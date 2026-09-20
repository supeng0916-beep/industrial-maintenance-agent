---
document_id: "doe-motor-ts09"
title: "Improve Motor Operation at Off-Design Voltages"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet9.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet9.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3736"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "c295cb8aa4b27ff6612c01577aafb4a5370cb4eee67d01c586ad1dfe2e9a7900"
---

# Improve Motor Operation at Off-Design Voltages

## Page 1

Improve Motor Operation at Off-Design Voltages

Motors are designed to operate within ± 10% of their nameplate rated voltages. When motors operate at conditions of over and undervoltage, motor efficiency and other performance parameters are degraded.

There are certain standard utilization voltages for motors. These correspond to (but are about 4% lower than) standard service voltages. The voltage difference is established to allow for a reasonable line voltage drop between the transformer secondary and the point of use, as shown in Table 1.

Motors sometimes come in multivoltage ratings. The different voltages are accom- modated by making different connections in the motor terminal box. For 1:2 ratios like 230/460, the connections change coil groups from parallel to series. For 1:1.73 ratios like 2,300/4,000, the connections change coil groups from delta (for the lower voltage) to wye (for the higher voltage). There is no difference in performance at the different voltage ratings because the different connection compensates to put the same total current through each winding turn. Tri-voltage motors (e.g., 208-230/460 volt [V]), are designed to produce rated torque at each voltage, but will slip more and operate hotter at 208 V than at 230 or 460 V. Additionally, some 230/460-V motors are marked “Usable on 208 Volts.” Note that the motor nameplate efficiency is measured at rated voltage and may be reduced when operating at a reduced voltage.

Table 1. Standard Motor Operating Voltages (Volts)

```text
  Service Voltage 208 240  480   600  2,400 4,160
 Utilization Voltage 200 230 460 575  2,300 4,000
```

What Happens to Motor Performance When Voltage Varies? With reduced voltage, torque capability is reduced over the whole accelerating range from initial start to full-load speed. This reduces a motor’s ability to produce sufficient starting torque and increases acceleration times. Full-load speed is only a fraction of a percent lower than normal, but torque is reduced by the square of the voltage ratio (operating voltage/nameplate voltage). A reduction in breakdown torque means the motor has less ability to drive through a brief torque overload without stalling. Low voltage caused by high system impedance is exacerbated during starting and acceleration when the current is four to eight times the nameplate full-load value.

As shown in Table 2, this power factor improves with undervoltage. This might be seen as a benefit, except the reduction in reactive current is more than nullified by the increase in the total current necessary to deliver the real power at reduced voltage. Higher cur- rents lead to increased resistance due to winding heating and power losses (I2R), reduced motor efficiency, and possible overheating at rated load conditions.

Slip also varies as the square of the voltage ratio. Slip is the difference between a motor’s actual speed and synchronous speed. Synchronous speed is always 7,200 revolutions per minute (RPM) divided by the pole count, for example, 3,600 RPM (two poles), 1,800 RPM (four poles), 1,200 RPM (six poles), 900 RPM (eight poles), etc. The actual synchronous speed always is the lowest possible synchronous speed above the nameplate full-load speed. For example, the synchronous speed for a 1,750 RPM motor

### Suggested actions / sidebar

Suggested Actions

• If voltage does not vary more than 3% to 5% but is constantly too high or too low, change to a different main service transformer tap setting. Adjust branch or secondary transformer tap settings as necessary.

• If daily voltage variation occurs at the service entrance, an “auto- tap-changer” transformer is recommended.

• If voltage is constant at the service entrance but varies within the facility due to load variations and distance from the transformer, replace existing conductors with larger ones or add parallel conductors as allowed by the National Electrical Code (NEC).

• For single motors attached to conventional motor starters, reduce voltage drops by installing power factor correction capacitors at the points of use.

• When using a motor with an electronic adjustable speed drive, the drive can compensate for voltage discrepancies as long as the input voltage is within the operating range of the drive.

• Have your service center rewind motors for the actual utilization voltage and evaluate the design for other ways to improve reliability and efficiency.

## Page 2

is 1,800, and the slip is 50 RPM. Running this motor at 10% overvoltage would increase the power draw for centrifugal fans and circulating pumps by approximately 1.5% because their power requirement is sensitive to operating speed. Refer to Motor Systems Tip Sheet #11, Adjustable Speed Drive Part-Load Efficiency, for additional information on the fan or affinity laws for centrifugal or variable torque loads.

Motor full-load efficiency is at a maximum between nominal voltage and about 10% overvoltage. However, at reduced load the best efficiency point shifts considerably toward lower voltages.

Sometimes, low voltage only occurs at remote areas of a facility where high loads are concentrated. In some cases, taps on power distribution transformers can be changed to adjust the delivered voltage to the desired utilization voltage. In new construction, or where correction of severe voltage drop is necessary, it may be practical to run medium voltage (> 600 to 6,600 V) distribution lines to the remote areas. Even though medium voltage in-plant distribution systems are subject to the same NEC maximum voltage drop of 3%, these systems are usually held to well under 1%. The medium voltage can be transformed down near the points of use, or the equipment can be driven by medium-voltage motors. Standard medium-voltage motors are available as small as 100 horsepower.

Table 2. General Effect of Voltage Variations on Induction Motor Performance (for General-Purpose Standard Efficiency Motors)

```text
                              Voltage Variation
     Motor Characteristic
                       90% of Nameplate 110% of Nameplate
Starting and Maximum Running Torque –19% +21%

      Starting Current     –10%         +10%

      Full-Load Current  +5% to +10%  –5% to –10%
     Full-Load Efficiency –1% to –3%  +1% to +3%

    Full-Load Power Factor +3% to +7% –2% to –7%

       Percent Slip        +22%         –19%
```

Source: Institute of Electrical and Electronics Enginners (IEEE) Standard 141-1993.

Additional Information For more information on ways to improve motor efficiency by improving the voltage supplied to the motor terminals, refer to Motor Systems Tip Sheet #7, Eliminate Voltage Unbalance.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www. nema.org for more information. When making the decision to start and stop a motor, refer to NEMA MG 10-2001, Energy Management Guide for Selection and Use of Fixed Frequency Medium AC Squirrel-Cage Polyphase Induction Motors. Also, refer to NEMA MG 1-2006, Motors and Generators Part 20.12.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
