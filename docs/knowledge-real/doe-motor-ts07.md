---
document_id: "doe-motor-ts07"
title: "Eliminate Voltage Unbalance"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/eliminate_voltage_unbalanced_motor_systemts7.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/eliminate_voltage_unbalanced_motor_systemts7.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3733"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "e39afc0a4f4a5e6e7d57baf219abd23eebce7a0b21f240337d0d6e70c232530a"
---

# Eliminate Voltage Unbalance

## Page 1

Eliminate Voltage Unbalance

Voltage unbalance degrades the performance and shortens the life of a three-phase motor. Voltage unbalance at the motor terminals can cause current unbalance that is far out of proportion to the voltage unbalance. Unbalanced currents lead to torque pulsations, increased vibrations and mechanical stresses, increased losses resulting in lower efficiency, and motor overheating, which reduces winding insulation life.

Percent voltage unbalance is defined by the National Electrical Manufacturers Association (NEMA) as 100 times the absolute value of the maximum deviation of the line voltage from the average voltage on a three-phase system, divided by the average voltage. For example, if the measured line voltages are 462, 463, and 455 volts, the average is 460 volts. The voltage unbalance is:

((460 – 455) / 460) x 100 = 1.1%

It is recommended that voltage unbalances at the motor terminals do not exceed 1%. Unbalances that exceed 1% require derating of the motor, per Figure 20-2 of NEMA MG-1-2011, and will void most manufacturers’ warranties. Common causes of voltage unbalance include:

• Faulty operation of power factor correction equipment

• Unbalanced or unstable utility supply

• Unbalanced transformer bank supplying a three-phase load that is too large for the bank

• Unevenly distributed single-phase loads on the same power system

• Unidentified single-phase to ground faults

• An open circuit on the distribution system primary.

The efficiency of an 1,800 revolutions per minute (RPM), 100-horsepower (hp) motor is given as a function of voltage unbalance and motor load in Table 1 below. The general trend of efficiency reduction with increased voltage unbalance is observed for motors at all load conditions.

Table 1. Example Motor Efficiency* Under Conditions of Voltage Unbalance

```text
                         Motor Efficiency, %
  Motor Load
                         Voltage Unbalance
    % Full
                Nominal       1%         2.5%
     100         94.4        94.4        93.0

     75          95.2        95.1        93.9

     50          96.1        95.5        94.1
```

Source: Washington State University Energy Program

*Results vary depending on motor design, speed, full-load efficiency, and hp rating. Typically, electric motors have peak efficiency near 75% load, but this particular motor tested in the lab showed otherwise.

### Suggested actions / sidebar

Suggested Actions

• Periodically monitor voltages at motor terminals to verify that voltage unbalance is maintained below 1%. Consider installing sensors that send alarms for unacceptable values or rates of change of values. ISA100 wireless sensor networks may be of interest.

• Check your electrical system single-line diagrams to verify that single-phase loads are uniformly distributed.

• Install ground fault indicators as required and perform annual thermographic inspections. Another indicator that voltage unbalance may be a problem is 120-hertz (Hz) vibration. A finding of 120-Hz vibration should prompt an immediate check of voltage balance.

## Page 2

Voltage unbalance is probably the leading power quality problem that results in motor overheating and premature motor failure. If unbalanced voltages are detected, a thorough investigation should be undertaken to determine the cause. Energy and cost savings occur when corrective actions are taken.

Voltage Unbalance Energy Savings Example Assume that the 100-hp motor tested as shown in Table 1 was fully loaded and operated for 8,000 hours per year (hrs/yr), with an unbalanced voltage of 2.5%. With energy priced at $0.08/kilowatt-hour (kWh), the annual energy and cost savings after corrective actions are taken are:

Annual Energy Savings = 100 hp x 0.746 kW/hp x 8,000 hrs/yr x (100/93 – 100/94.4) = 9,517 kWh

Annual Cost Savings = 9,517 kWh x $0.08/kWh = $760

Overall savings may be much larger because an unbalanced supply voltage may power numerous motors and other electrical equipment.

Further Considerations Voltage unbalance causes extremely high current unbalance. The magnitude of current unbalance may be 6 to 10 times as large as the voltage unbalance. For the 100-hp motor in the preceding example, line currents (at full load with 2.5% voltage unbalance) were unbalanced by 27.7%.

A motor will run hotter when operating on a power supply with voltage unbalance. The additional temperature increase is estimated with the following equation1:

Total Temperature Rise = Balanced Temperature Rise x (1 + 2 x (% Voltage Unbalance)^2/100)

For example, a motor with an 80°C temperature rise caused by resistance would experience a temperature increase of 6.4°C when operated under conditions of 2% voltage unbalance. Winding insulation life is reduced by one-half for each 10°C increase in operating temperature.2

References 1Reliance Electric, “Power Supply” September, 1998.

2“Stopping a Costly Leak: The Effects of Unbalanced Voltage on the Life and Efficiency of Three-Phase Electric Motors.” Energy Matters. U.S. Department of Energy. Winter 2005.

Additional References Information in this tip sheet is extracted from NEMA Standards Publication MG-1-2011, Motors and Generators, which is available for purchase from www.nema.org.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www.nema.org for additional information on voltage imbalance.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
