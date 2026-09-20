"""Build/query/evaluate local maintenance document retrieval, without an LLM."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def build(manifest, output, model_key, download=False, cache_dir=None):
    from .knowledge_documents import load_documents
    from .knowledge_preview import check_coverage
    from .rag_chunks import build_rag_chunks, STRATEGY
    from .rag_embeddings import LocalEmbedder
    from .rag_index import create_index
    manifest,output=Path(manifest).resolve(),Path(output).absolute()
    if output.exists() or output.is_symlink():raise FileExistsError(f'index already exists: {output}')
    if output.resolve().is_relative_to(manifest.parent):raise ValueError('index must be outside source corpus')
    documents=load_documents(manifest)
    if not documents:raise ValueError('manifest contains no documents')
    embedder=LocalEmbedder(model_key,download=download,cache_dir=cache_dir)
    chunks=build_rag_chunks(documents,embedder.tokenizer,format_passage=embedder.format_passage)
    coverage=check_coverage(documents,chunks)
    corpus=dict(manifest=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                documents=coverage,chunk_strategy=STRATEGY,max_token_count=max(c['token_count'] for c in chunks),
                over_soft_target=sum(c['token_count']>300 for c in chunks),
                physical_pages=sum(len(d['metadata'].get('source_pages',[])) for d in documents),
                source_pages_note='Count from document metadata; inspect source registration for duplicates.')
    return create_index(output,chunks,embedder,corpus)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--manifest',type=Path,required=True)
    q=sub.add_parser('query');q.add_argument('--query',required=True);q.add_argument('--top-k',type=int,default=5)
    q.add_argument('--filters',default='{}',help='JSON object: document_id/language/publisher/product_model/device_id/teaching_only/source_document_id')
    e=sub.add_parser('evaluate');e.add_argument('--cases',type=Path,required=True);e.add_argument('--output',type=Path,required=True)
    for command in (b,q,e):
        command.add_argument('--index',type=Path,required=True)
        command.add_argument('--model',choices=['e5','bge'],required=command is b)
        command.add_argument('--download-model',action='store_true')
        command.add_argument('--model-cache',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='build':
            config=build(args.manifest,args.index,args.model,args.download_model,args.model_cache)
            result=dict(ok=True,index=str(args.index),config=config)
        else:
            from .rag_index import read_index,search_index
            from .rag_embeddings import LocalEmbedder,MODEL_SPECS
            config,_=read_index(args.index)
            key=args.model or next((k for k,v in MODEL_SPECS.items() if v['model']==config['model_signature'].get('model')),None)
            if key is None:raise ValueError('index uses an unsupported model signature')
            if args.command=='evaluate' and (args.output.exists() or args.output.is_symlink()):
                raise FileExistsError(f'evaluation output already exists: {args.output}')
            embedder=LocalEmbedder(key,download=args.download_model,cache_dir=args.model_cache)
            if args.command=='query':
                result=search_index(args.index,args.query,embedder,top_k=args.top_k,filters=json.loads(args.filters))
            else:
                from .rag_evaluation import evaluate_index
                result=evaluate_index(args.index,args.cases,embedder)
                args.output.parent.mkdir(parents=True,exist_ok=True)
                with args.output.open('x',encoding='utf-8') as stream:
                    json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
                result=dict(ok=True,output=str(args.output),summaries=result['summaries'])
    except Exception as exc:
        print(json.dumps(dict(ok=False,error=dict(type=type(exc).__name__,message=str(exc))),ensure_ascii=False))
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0


if __name__=='__main__':
    sys.exit(main())
