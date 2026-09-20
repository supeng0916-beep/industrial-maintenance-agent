---
document_id: "doe-motor-ts15"
title: "Minimize Adverse Motor and Adjustable Speed Drive Interactions"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet15.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet15.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3739"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "d76af015ec57e5ef868834103297534a8d64a77418a0995de248d7af3e7a5285"
---

# Minimize Adverse Motor and Adjustable Speed Drive Interactions

## Page 1

Minimize Adverse Motor and Adjustable Speed Drive Interactions

Electronic adjustable speed drives (ASDs) are extremely efficient and valuable assets to motor systems. They allow precise process control and provide energy savings within systems that do not need to operate continuously at full output.

The most common ASD design sold today is the pulse-width-modulated (PWM) variable frequency drive (VFD) with a fast-rise-time insulated gate bipolar transistor (IGBT) to reduce switching losses and noise levels. However, higher carrier frequencies and faster rise-time transistors on PWM VFDs can produce voltage spikes or overshoots that can stress motor windings and bearings. Fortunately, these problems can be eliminated through proper design and equipment selection.

VFD Characteristics All VFDs rectify the 60-hertz (Hz) fixed-voltage alternating current (AC) to direct current (DC) and use an inverter to simulate an adjustable frequency and variable- voltage AC output. Transistors, or electronic “switches,” create the AC voltage output but have very high losses when they create wave shapes other than square waves.

Figure 1. Sine wave overlaid on square carrier waves

To minimize switching losses and approximate sine waves, VFDs operate these switches full-on or full-off, creating square waves of much higher frequency than the fundamental frequency, usually between 2 kilocycles per second (kHz) and 20 kHz. This is called a carrier wave, as shown in Figure 1. Each on-portion of the carrier wave is called a pulse, and the duration of on-time of each pulse is called the pulse width. The pulses do not turn on instantaneously; there is a brief rise time.

Different types of transistors used in drives have different rise times. Voltage spikes originate with fast rise time, and carrier frequencies above 5 kHz are likely to cause bearing damage unless protective measures are taken.

Design Considerations Several design considerations should be taken into account when purchasing a VFD or fixing problems with an existing one. On new installations, ensure that no harm comes to motors by minimizing the cable length from the VFD to the motor. VFDs can produce voltage overshoots or spikes with the increase over the normal peak voltage dependent upon both cable length and rise time. lamroN revO esaercnI reilpitluM egatloV kaeP 2.00

1.80 500’ Cable 1.60 200’ Cable 1.40 100’ Cable 1.20 5500’’ CCaabbllee

1.00

Rise Time (µs) TTBBGGII

1.0 2.0 3.0 4.0 5.0

### Suggested actions / sidebar

Suggested Actions

• To best avoid or mitigate voltage overshoots, consider locating the drive close to the motor. Where this is not possible, consider installing filtering devices such as:

– Line inductors or load reactors at the drive end of the cable

– dV/dt filters.

• Consider purchase of an inverter- duty motor. See Motor Systems Tip Sheet #14 When Should Inverter-Duty Motors Be Specified? for inverter-duty motor performance standards.

• Minimize or eliminate problems of current flow across the rolling elements of the motor’s bearings by isolating both bearings and/or using a shaft-grounding brush. Install the insulated bearing arrangement and shaft grounding brush on the in-service motor and any designated spare.

• VFDs with oscillating carrier frequencies may contribute to bearing current flows. Correct setup of the drive and proper cabling and grounding practices may help reduce bearing damage, called fluting, which occurs as a result of VFD- induced shaft currents.

## Page 2

Rise Time (µs)

Figure 2. Effect of cable length on voltage increase Source: John Fluke Manufacturing Company

In Figure 2, the voltage increase is plotted against rise time in microseconds. Rise time is the time required for the voltage to increase from 10% to 90% of its steady- state value. The rise time is a characteristic of the power transistor switches and can be provided by the drive supplier. Modern IGBT switches operate well down toward the left side of the graph, so cable lengths of 50 feet or more almost always need mitigation.

Longer cables reflect the voltage rise so that the reflections reinforce the original pulse rise. This produces electrical resonance or “ringing” characterized by an oscillating voltage overshoot. With shorter cables, rapid rise time is not a problem. Review Figure 2 to determine voltage increase for a given rise time and cable length, and compare the result with the maximum values described below.

Existing general-purpose low-voltage motors may work fine with PWM VFDs if peak voltages due to ringing are held below 1,000 volts. If high-frequency voltage overshoots exceed 1,000 volts, electrical stresses can cause a turn-to-turn short within a motor coil group, usually within the first couple of turns.

Voltage overshoot is best avoided by locating the drive close to the motor. If a short cable run is not possible, a filtering device must be used. Sometimes VFD manufacturers provide a filter device with the drive or even in the drive cabinet. There are two common filter arrangements: the first uses line inductors (sometimes called load reactors), which should be placed at the drive end of the cable; and the second uses dV/dt filters. A tuned resistor- inductor filter increases the voltage rise time and effectively reduces dV/dt. There are some losses associated with the filters, so keeping cables short remains the best option.

The fast rise time pulses from a PWM VFD can also create a potentially harmful current flow in bearings even when overvoltage is not significant. Causes include common mode voltage problems and/or phase voltage unbalance on the VFD input. Capacitive coupling, resulting from irregular current waveforms and ground-mode currents, can damage bearings due to formation of a high-frequency voltage potential on the motor shaft that results in current flow across the bearing rolling elements. Problems also can occur in driven-load bearings if insulated couplings are not used. Reduce these problems by:

• Reducing the carrier frequency of the VFD to between 2 kHz and 5 kHz

• Using a dedicated, low-impedance ground wire from the motor frame to the case drives

• Selecting a suitable cable (i.e., symmetrical with all three phases equally spaced around the ground conductor)

• Selecting and matching cable impedance for the VFD.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www. nema.org for information on motor standards, application guides, and technical papers.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
