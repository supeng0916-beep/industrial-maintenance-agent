"""Visually verified transcription fixes. No translation or semantic rewriting."""
import re

def normalize(n, page, text):
    text=text.replace('wind- ing','winding').replace('eleva- tions','elevations').replace('adjust- able','adjustable') # only reviewed line-end hyphenations
    if n==3 and page==2:
        text=text.replace('A bearing L is defined by International Organization for Standardization (ISO) and 10','A bearing L10 is defined by International Organization for Standardization (ISO) and')
        text=text.replace('the L rating of a bearing may be cause for concern. For fixed 10h','the L10h rating of a bearing may be cause for concern. For fixed')
        text=text.replace('a longer L rating implies a longer bearing life. The bearing 10h','a longer L10h rating implies a longer bearing life. The bearing')
    if n==7 and page==1:
        text=text.replace('(460 – 455) x 100 = 1.1% 460','((460 – 455) / 460) x 100 = 1.1%')
    if n==7 and page==2:
        text=text.replace('(% Voltage Unbalance)2/100','(% Voltage Unbalance)^2/100')
    if n==11 and page==1:
        start=text.index('hp = hp x '); end=text.index('\n\nFigure 1.',start)
        text=text[:start]+'''hp_2 = hp_1 x (RPM_2/RPM_1)^3 = hp_1 x (Flow_2/Flow_1)^3

Where:

- hp_1 = driven-equipment shaft horsepower requirement at original operating speed
- hp_2 = driven-equipment shaft horsepower requirement at reduced speed
- RPM_1 = original speed of driven equipment, in revolutions per minute (RPM)
- RPM_2 = reduced speed of driven equipment, in RPM
- Flow_1 = original flow provided by centrifugal fan or pump
- Flow_2 = final flow provided by centrifugal fan or pump'''+text[end:]
    if n==11 and page==2:
        text=text.replace('(ηsystem = η x VFD η x η ). Efficiencies for integral horsepower NEMA Design A and B motors Motor Equipment','(η_system = η_VFD x η_Motor x η_Equipment). Efficiencies for integral horsepower NEMA Design A and B motors')
    return text
