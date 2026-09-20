---
document_id: "doe-motor-ts02"
title: "Estimating Motor Efficiency in the Field"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/estimate_motor_efficiency_motor_systemts2.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/estimate_motor_efficiency_motor_systemts2.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3734"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "ae69737fc301d2dce437c98b803c857b70a48134be886b884d09d2122e5a4533"
---

# Estimating Motor Efficiency in the Field

## Page 1

Estimating Motor Efficiency in the Field

Some utility companies and public agencies offer rebates to encourage customers to upgrade their existing standard efficiency motors to premium efficiency motors. It is important to know the efficiency of the existing motor and how it is being used to accurately estimate potential annual energy and dollar savings.

Efficiency is defined as output power divided by input power. By using applicable and acceptable methods and devices, motor efficiency values can be obtained at full and part load. This includes testing populations of motors on a dynamometer or measuring electrical losses under controlled laboratory conditions. While laboratory testing provides a basis for comparison of motor efficiencies, these motor efficiency values should not be interpreted as the actual efficiency of the motor while under load in a particular application.

Nevertheless, efficiency should be measured accurately because, as shown in Table 1, a single percentage point of improved efficiency provides significant dollar savings even for small motors. A quality electric power meter, properly calibrated, can determine motor input power to an accuracy of ±1%. Unfortunately, an inexpensive, portable way to measure shaft output power of a motor that is coupled to a piece of equipment, such as a printing press, does not exist. A further complication is that motor efficiency is dependent upon loading, power quality, and ambient temperature.

Table 1. What Is an Extra Percentage Point of Motor Efficiency Improvement Worth?

```text
           Motor Efficiency at 75% Load Annual Savings

 Horsepower                   Annual Energy
            Original   Final            Dollar Savings
                                Savings,
            Efficiency Efficiency         $/year
                                 kWh
    10       92.2      93.2      520       40
    25       93.8      94.8      1,260     100
    50       95.0      96.0      2,455     195

    100      95.3      96.3      4,875     390
    200      96.2      97.2      9,575     765
```

Note: Based on operation of a 1,800 revolutions per minute (RPM) totally enclosed fan-cooled (TEFC) motor with an efficiency 1.0% higher than that of a typical premium efficiency motor with 8,000 hours per year of operation, 75% load, and an electrical rate of $0.08/kilowatt-hour (kWh).

Credible efficiency ratings are normally obtained in a laboratory, following carefully controlled dynamometer testing procedures as described in Institute of Electrical and Electronics Engineers (IEEE) Standard 112-2004 (Test Method B). Field measurements for determining motor efficiency pose challenges that require developing various other methods and devices.

### Suggested actions / sidebar

Suggested Actions

• Conduct predictive maintenance monitoring and tests to reveal if efficiency is below the original or nameplate level. Decreased efficiency may be due to:

– Higher winding resistance compared with either manufacturer specifications or an earlier measurement. This may be caused by motor windings operating at a higher temperature than that of the manufacturer’s resistance specifications or by rewinding with smaller diameter wire. Use a low-resistance ohmmeter when measuring winding resistance values.

– Increase in no-load power or core losses. Core loss testing requires motor disassembly and is performed in a motor service center.

– Significant current unbalance when voltage is balanced.

– Evidence of rotor cage damage.

– Line voltages that are unbalanced, overvoltage, or undervoltage.

## Page 2

Motor losses fall into several categories that can be measured in various ways:

• Stator winding resistance (I2R) losses

• Rotor conductor bar and end ring resistance (I2R) losses

• Stator and rotor core losses

• Friction and windage losses (including bearing losses, wind resistance, and cooling fan load)

• Stray load losses (miscellaneous other losses).

The most direct and credible methods of measuring these losses involve considerable labor, equipment, and the availability of electrical power. Power readings must be taken with the motor running under load, then uncoupled and running unloaded. Winding resistance must be measured and temperature corrections must be performed.

Simpler but less accurate motor efficiency estimation techniques are available. They require fewer field measurements and don’t involve uncoupling the motor from the load. These techniques include:

• Loss accounting methods. Such methods determine losses using either special dedicated “lab-in-a-box” devices or very accurate conventional instruments, including power meters, thermometers, and micro-ohmmeters. These methods have the potential of being accurate within ±1% to ±3% if carefully applied. The necessary instruments are costly, and the process is very time and labor intensive. Power meters must be accurate at very low power factors that occur when motors operate unloaded.

• Slip method. The slip method has largely been discredited as a viable technique for estimating motor efficiency. This method computes shaft output power as the rated horsepower multiplied by the ratio of measured slip to the slip expected when the motor is fully loaded. Operating slip is the difference between synchronous and shaft speed, with the full-load slip equal to the difference between the synchronous speed and the full-load speed stamped on the motor nameplate.

• MotorMaster+ 4.0. This software tool, developed by the U.S. Department of Energy’s (DOE) Advanced Manufacturing Office (AMO), incorporates several methods for determining motor load. These involve the use of motor nameplate data in conjunction with field measurements of input power, voltage, current, and/or operating speed. MotorMaster+ 4.0 automatically selects the best of four available load and efficiency estimation methods based on the data entered. Once the percent load is known, the software tool obtains efficiency values from embedded default part-load efficiency tables. Default efficiency tables are available for motors of different enclosure types (open drip-proof and TEFC), horsepower ratings, synchronous speeds, and efficiency classes.

### Resources / sidebar

Resources

U.S. Department of Energy (DOE)— For additional information on motor and motor-driven system efficiency measures, to obtain DOE’s MotorMaster+ software, or to learn more about training, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
