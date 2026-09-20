---
document_id: "doe-motor-ts14"
title: "When Should Inverter-Duty Motors Be Specified?"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet14.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet14.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3744"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "46029534abfbb5be5da1d54fecbd737c41bedd611d5e99dd09f1cd51faa51b58"
---

# When Should Inverter-Duty Motors Be Specified?

## Page 1

When Should Inverter-Duty Motors Be Specified?

Electronic adjustable speed drives, known as variable frequency drives (VFD), used to be marketed as “usable with any standard motor.” However, premature failures of motor insulation systems began to occur as fast-switching, pulse-width-modulated (PWM) VFDs were introduced. The switching rates of modern power semiconductors can lead to voltage overshoots. These voltage spikes can rapidly damage a motor’s insulation system, resulting in premature motor failure.

Effects of VFDs on Induction Motors The nonsinusoidal variable frequency output of PWM drives has several effects, including increased motor losses, inadequate ventilation at lower speeds, increased dielectric stresses on motor windings, magnetic noise, and shaft currents. These effects can combine to damage a motor’s insulation and severely shorten its useful operating life.

High switching rates of modern power semiconductors lead to rapid changes in voltage in relatively short periods of time, (dV/dt, quantified in units of volts per microsecond). Steep- fronted waves with large dV/dt or very fast rise times lead to voltage overshoots and other power supply problems.

When the motor impedance is greater than the impedance of the conductor cable between the motor and the drive, the voltage waveform will reflect at the motor terminals. This creates a standing wave (see Figure 1). Longer motor cables favor higher amplitude standing waves. Voltage spikes have occurred with peak values as high as 2,150 volts (V) in a 480-V system operating at 10% overvoltage. These high spikes can lead to insulation breakdown, which results in phase-to-phase or turn-to-turn short circuits, and subsequently overcurrent drive sensor trips.

Figure 1. PWM pulse with reflected voltage or ringing

Preventive measures can be taken to avoid motor failures caused by voltage spikes. These include using power conditioning equipment (such as dV/dt filters or load reactors) and restricting the distance or cable length between the drive and the motor. Some drive installers also specify oversized motors or use of high-temperature resistance Class H insulation.

Inverter-Duty Motor Designs Most motor manufacturers offer general-purpose, three-phase premium efficiency motors that feature “inverter-friendly” insulation systems. These “inverter-ready” motors are suitable for use with variable torque loads over a wide speed range.

In contrast, inverter-duty motors are wound with voltage spike-resistant insulation systems.

### Suggested actions / sidebar

Suggested Actions

• Obtain information from motor and drive manufacturers about inverter rise times and effects of cable length. Use this informa- tion to evaluate the capacity of existing motors to withstand drive-induced voltage stresses.

• Damaging reflected waves are generally not a problem when the distance between the motor and the drive is less than 15 feet.

• Voltage overshoots are more likely to occur with smaller motors and drives with faster rise times.

• The potential for damaging reflected waves is especially high when multiple motors are run from a single VFD.

## Page 2

by VFDs. Other designs are wound with adjacent coils that are separated to minimize voltage potential. Improved insulation systems reduce degradation of motors that are subjected to transient voltage spikes. A greater thickness or buildup of premium varnish (through multiple dips and bakes) minimizes the potential for internal voids, and a motor with a lower heat rise design has increased resistance to voltage stresses. Manufacturing quality also affects the corona inception voltage (CIV), the point at which partial electrical discharges occur because of ionization of air around the conductor. CIV is a measure of the ability of a motor’s windings to withstand voltage stresses.

NEMA MG 1-2011, Part 31, specifies that insulation systems for definite-purpose, low- voltage (≤ 600 V) inverter-duty motors should be designed to withstand an upper limit of 3.1 times the motor’s rated line-to-line voltage. This is equivalent to an upper limit of 1,426 peak volts at the motor terminals for a motor rated at 460 V. Rise times must equal or exceed 0.1 microsecond. These motors can be used without additional filters or load reactors provided that voltage overshoots do not exceed the upper limit at the motor terminals.

Medium-voltage inverter-duty motors with a base rating that exceeds 600 V must be able to withstand a peak voltage equal to 2.04 times the motor’s rated line-to-line voltage. Rise times must equal or exceed 1 microsecond.

Inverter-duty motors are also designed for wider constant-torque speed ranges than can be provided with a general-purpose motor. While a premium efficiency, totally enclosed fan- cooled 10-hp motor may be capable of a 10:1 constant-torque speed range, an inverter-duty motor is capable of providing full-rated torque at zero speed as well as operating well over its base speed. Use of inverter-duty motors for variable torque loads is overkill as inverter-ready general-purpose motors are well suited for VFD control with variable torque loads.

The insulation system on a 208/230-V motor is identical to that of a 460-V motor. Thus, voltage spikes produced by inverters on 208- or 230-V systems are unlikely to cause insulation damage at any cable length or drive carrier frequency.

Larger inverter-duty motors often have a constant-speed auxiliary blower to provide adequate cooling for motors operating at low speeds. Above the 500 frame size, inverter-duty motors should have both bearings insulated and be equipped with a shaft grounding brush with a ground strap from the motor to the drive case.

```text
               Motor Selection Guidelines

NEMA MG 1-2011, Part 30, provides performance standards for general-purpose
motors used with VFDs. When operated under usual service conditions, no
significant reduction in service life should occur if the peak voltage at the motor
terminals is limited to 1,000 V and rise times equal and exceed 2 microseconds.
Contact the motor manufacturer for guidance on motor/drive compatibility when
peak voltages are expected to exceed 1,000 V or rise times will be less than 2
microseconds. A definite-purpose, inverter-duty motor and/or harmonic suppression
filter, load reactor, or other voltage conditioning equipment may be required.
Specify inverter-duty motors when operating at extremely low speeds, particularly
when serving a constant torque load, or when operating over base speed.
When an inverter-duty motor is required, ensure that it is designed and
manufactured to meet the most current specifications defined by NEMA MG 1
Section IV, “Performance Standards Applying to All Machines,” Part 31, “Definite-
Purpose Inverter-Fed Polyphase Motors.”
```

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www. nema.org for information on motor standards, application guides, and technical papers. Refer to the 2001 NEMA Standards Publication Application Guide for AC Adjustable Speed Drives.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
