---
document_id: "doe-motor-ts11"
title: "Adjustable Speed Drive Part-Load Efficiency"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet11.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet11.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3730"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "2614ca8b880e4f8962b45e9a832e0800e73db3300cbe892111d6b6aa9d7c3c0d"
---

# Adjustable Speed Drive Part-Load Efficiency

## Page 1

Adjustable Speed Drive Part-Load Efficiency

An adjustable speed drive (ASD) is a device that controls the rotational speed of motor-driven equipment. Variable frequency drives (VFDs), the most common type of ASD, are solid-state electronic motor controllers that efficiently meet varying process requirements by adjusting the frequency and voltage of power supplied to an alternating current (AC) motor to enable it to operate over a wide speed range. External sensors monitor flow, liquid levels, or pressure and then transmit a signal to a controller that adjusts the frequency and speed of the motor to match process requirements.

Variable Torque Loads Pulse-width-modulated (PWM) VFDs are most often used in variable torque applications in the 1 to 1,000 horsepower (hp) motor size range. For centrifugal fans or pumps with no static lift, the fan or affinity laws state that the fluid or airflow provided varies directly with the pump or fan rotational speed. The input power requirement varies as the cube or third power of the speed ratio, as shown in Figure 1. Small decreases in equipment rotating speed or fluid flow yield significant reductions in energy use. For example, reducing rotating equipment speed (flow) by 20% can reduce input power requirements by approximately 50%.

hp_2 = hp_1 x (RPM_2/RPM_1)^3 = hp_1 x (Flow_2/Flow_1)^3

Where:

- hp_1 = driven-equipment shaft horsepower requirement at original operating speed
- hp_2 = driven-equipment shaft horsepower requirement at reduced speed
- RPM_1 = original speed of driven equipment, in revolutions per minute (RPM)
- RPM_2 = reduced speed of driven equipment, in RPM
- Flow_1 = original flow provided by centrifugal fan or pump
- Flow_2 = final flow provided by centrifugal fan or pump

Figure 1. Power requirement for variable torque loads

Constant Torque Loads A constant torque load is one where the torque requirement is independent of speed. Because horsepower requirements equal the product of required torque and speed, input power varies linearly with speed for constant torque applications. Examples of constant torque loads include cranes, hoists, conveyors, extruders, mixers, positive displacement pumps, reciprocating air compressors, and rotary screw air compressors.

Determining Energy Savings To establish the energy savings that are possible when a VFD is applied to a variable or constant torque load, you must determine the load duty cycle, or percentage of time that the driven equipment operates at each system operating point. You must also know the efficiency of the variable speed drive and the drive motor when the motor is operating partially loaded and at a reduced speed to satisfy variable flow requirements.

When considering PWM VFDs, you may use manufacturer’s data or Table 1 to obtain efficiency values for drives of various ratings that supply power to motors connected to either variable or constant torque loads. Note that motor efficiency is also reduced at light loads and when the motor is supplied with a nonsinusoidal waveform.

### Suggested actions / sidebar

Suggested Actions

• Contact your supplier to obtain information about drive efficiency as a function of motor operating speed or drive power output.

• When VFD part-load performance values are not readily available, use the values given in Table 1. Use this information to accurately determine the energy savings due to the use of VFD versus throttle or damper flow control.

• Drive Performance Variable and constant torque loads are expressed in terms of the shaft horsepower supplied by the motor. A motor “load” is the brake or shaft power requirement imposed upon the motor by the driven equipment divided by the motor’s full horsepower rating. The load on the ASD is the actual power supplied by the device (shaft horsepower divided by the motor efficiency at its load point) divided by the drive rated output power. Drive distributors or manufacturers can provide efficiency values for ASDs as a function of operating speed or load for both variable and constant torque loads.

## Page 2

Table 1. Adjustable Speed Drive Part-Load Efficiency*

```text
                       Efficiency (%)
 Variable
  Drive        Load, Percent of Drive Rated Power Output
hp Rating
          1.6  12.5  25    42    50   75    100
   5      35   80    88    91    92   94    95
   10     41    83   90    93    94   95    96
   20     47    86   93    94    95   96    97
   30     50    88   93    95    95   96    97
   50     46    86   92    95    95   96    97

  60      51    87   92    95    95   96    97
   75     47    86   93    95    96   97    97
  100     55    89   94    95    96   97    97

  200     61    81   95    96    96   97    97
```

*These efficiency values may be considered representative of “typical” PWM VFD performance. There is no widely accepted test protocol that allows for efficiency comparisons between different drive models or brands. In addition, there are many ways to set up a VFD that can affect the operating efficiency. Source: Saftronics, Inc.

VFD efficiency decreases with decreasing motor load. The decline in efficiency is more pronounced with drives of smaller horsepower ratings. As shown in the following example, this reduction in efficiency is not as detrimental as it first seems.

Example Consider a VFD coupled to a motor that requires 16.4 kilowatts (kW) to deliver 20 shaft hp to an exhaust fan when operated at its full rated speed. At half its rated operating speed, the fan delivers 50% of its rated airflow but requires only 1/8 full-load power. Even with a reduced motor efficiency of 77.8% and drive efficiency of 86%, with adjustable speed operation the power required by the fan and the VFD is only 2.8 kW. For this example, input power requirements are reduced by 82.9%.

kW 50% = 0.746 kW/hp x (20 hp x (1/2)3 / (0.778 x 0.86) = 2.8 kW

Remember that the system efficiency is the product of the VFD efficiency, the motor efficiency at its load point, and the driven equipment efficiency (η_system = η_VFD x η_Motor x η_Equipment). Efficiencies for integral horsepower NEMA Design A and B motors at full and part load can readily be obtained from the U.S. Department of Energy’s MotorMaster+ 4.0 software tool. Efficiencies for driven equipment must be extracted from the appropriate pump or fan performance curves.

Additional Information For additional information regarding adjustable speed drive applications, refer to Motor Systems Tip Sheet #14, When Should Inverter-Duty Motors be Specified and Motor Systems Tip Sheet #15, Minimize Adverse Motor and Adjustable Speed Drive Interactions at: www.eere.energy.gov/manufacturing/tech_deployment/motors.html.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www. nema.org for information on motor standards, application guides, and technical papers.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
