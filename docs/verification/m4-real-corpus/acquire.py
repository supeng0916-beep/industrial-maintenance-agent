import urllib.request, concurrent.futures, pathlib, hashlib, json
ROOT=pathlib.Path(__file__).resolve().parents[3]
RAW=ROOT/'docs/verification/m4-real-corpus/raw'
FILES=['whentopurchase_nema_motor_systemts1.pdf','estimate_motor_efficiency_motor_systemts2.pdf','extend_motor_operlife_motor_systemts3.pdf','importance_motor_shaft_motor_systemts4.pdf','replace_vbelts_motor_systemts5.pdf','avoid_nuisance_motorsys_ts6.pdf','eliminate_voltage_unbalanced_motor_systemts7.pdf','motor_tip_sheet8.pdf','motor_tip_sheet9.pdf','motor_tip_sheet10.pdf','motor_tip_sheet11.pdf']
FILES += [f'motor_tip_sheet{n}.pdf' for n in range(12,16)]
def get(item):
 n,f=item; url='https://www.energy.gov/sites/prod/files/2014/04/f15/'+f; p=RAW/f'doe-motor-tip-{n:02}.pdf'
 if not p.exists():
  with urllib.request.urlopen(url, timeout=60) as r: b=r.read()
  assert b.startswith(b'%PDF'); p.write_bytes(b)
 return {'tip':n,'url':url,'raw':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex: results=list(ex.map(get,enumerate(FILES,1)))
(ROOT/'docs/verification/m4-real-corpus/downloads.json').write_text(json.dumps(results,indent=2)+'\n')
print('Downloaded',len(results))
