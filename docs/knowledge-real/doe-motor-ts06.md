---
document_id: "doe-motor-ts06"
title: "Avoid Nuisance Tripping with Premium Efficiency Motors"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/avoid_nuisance_motorsys_ts6.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/avoid_nuisance_motorsys_ts6.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3731"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "03f9eeef5f3b1446134636c8f6be601d651706fe1e8bc33f50fbdc50496b56bb"
---

# Avoid Nuisance Tripping with Premium Efficiency Motors

## Page 1

Avoid Nuisance Tripping with Premium Efficiency Motors

In most cases, upgrading to premium efficiency motors has no noticeable impact on the electrical system. However, in rare cases nuisance trips can occur during start-up. Addressing this topic requires an understanding of starting current.

The National Electrical Manufacturers Association (NEMA) recognizes and describes two components of starting current: instantaneous peak inrush and locked rotor current (LRC). Nuisance tripping primarily has been associated with the instantaneous peak inrush, which is a momentary current transient that occurs immediately (within half an AC cycle) after contact closure. LRC is the root-mean-square (RMS) current that is established following the peak inrush; the current remains near the locked rotor value during acceleration until the motor approaches its operating speed. (Note: The terms inrush or starting current are often used to mean locked rotor current.)

Premium efficiency motors have slightly higher LRCs and locked rotor code letters than lower efficiency motors of the same rating. However, most premium efficiency motors are NEMA Design B and are subject to the same maximum allowable LRC as their standard efficiency counterparts. LRC for specific new motor models can be looked up in the U.S. Department of Energy’s (DOE) Advanced Manufacturing Office’s (AMO) MotorMaster+ 4.0 software tool or deciphered from the locked-rotor code letter on the motor nameplate. This letter, usually just designated as “code,” is not the same as the motor design letter code. Locked rotor code expresses current in kilovolt-amperes (kVA) per horsepower (hp), or kVA/hp. International Electrotechnical Commission (IEC) or metric motors do not use NEMA-defined code letters. The NEMA code letters are defined as follows:

Table 1. NEMA Locked-Rotor Code Letters

```text
                 Locked-Rotor Code, kVA/hp

              A   0–3.15   G   5.6–6.3

              B   3.15–3.55 H   6.3–7.1
              C   3.55–4.0  I   7.1–8.0

              D   4.0–4.5   J  8.0–9.0

              E   4.5–5.0   K  9.0–10.0
              F   5.0–5.6   L  10.0–11.2
```

For example, the maximum LRC for a Code C, 460-volt, 100-hp motor is determined as follows:

LR Current = Motor Horsepower x (Maximum kVA/hp/Supply Voltage in kV) / √3 = 100 hp x {(4.0 kVA/hp / 0.46 kV) / √3} = 502 Amps

### Suggested actions / sidebar

Suggested Actions

• Make sure power factor correction capacitors are installed ahead of the starter.

• Refer to Section 430 of the latest National Electrical Code (NEC) for guidance on increasing the instantaneous trip level of your circuit protector. The code has been modified to allow adjustments to a greater allowable trip setting when nuisance trips occur. Note that the code can be complicated and exceptions do exist. Don’t hesitate to contact a licensed professional electrical engineer to resolve motor protection problems.

• If adjusting the trip setting is not sufficient, consider replacing the circuit protector with one that has a mechanical delay that allows the motor to ride through half a cycle of current above the nominal setting.

## Page 2

The NEMA table, from NEMA MG 1-2011 Motors and Generators, which is available for purchase from www.nema.org, actually continues all the way to letter V with current increasing about 12.3% for each letter increment. Only small and non-NEMA Design B motors have codes beyond L.

The ratio of peak inrush to LRC tends to increase with higher efficiency motors due to their lower power factor under locked rotor conditions.

While NEMA Design B standards limit LRC, no standard limits the peak-inrush current. Fortunately, peak-inrush current usually is not a problem because it lasts only a few milliseconds. However, it can be an issue when the motor controller uses instantaneous magnetic-only circuit protectors that react in less than a single AC cycle. This is because peak inrush can be as high as 2.8 times the RMS locked rotor current and may exceed the circuit protector current setting.

A motor may trip on peak-inrush current and start successfully on the next attempt. The exact peak-inrush current depends on the moment when contacts close in the AC voltage cycle, and how close to simultaneously the three-phase contacts close.

Nuisance trips are unlikely to occur in situations without instantaneous magnetic-only circuit protectors when the replacement motor is a premium efficiency Design B motor of the same speed and horsepower as the original unit. Even if instantaneous magnetic- only circuit protectors are present, nuisance trips may not happen. Nuisance trips should not be an issue with motors that are controlled with soft starters or adjustable speed drives. Many motor manufacturers offer premium efficiency Design A motors that meet Design B torque requirements but exceed Design B locked-rotor current limits. Some of the most efficient motors are Design A, which do not have inrush current restrictions, so do not limit choices to Design B unless LRC concerns exist.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—For information on premium efficiency motor standards, see Motor Systems Tip Sheet #1 entitled When to Purchase Premium Efficiency Motors or visit www.nema.org.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
