---
document_id: "doe-motor-ts08"
title: "Eliminate Excessive In-Plant Distribution System Voltage Drops"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet8.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet8.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3732"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "9119468e2237aae542d8d2fe2905c1de6fd0788fe42af59609792f6995b8f448"
---

# Eliminate Excessive In-Plant Distribution System Voltage Drops

## Page 1

Eliminate Excessive In-Plant Distribution System Voltage Drops

Studies indicate that in-plant electrical distribution system losses—due to voltage unbalance, over- and undervoltage, low power factor, undersized conductors, leakage to ground, and poor connections—can account for less than 1% to more than 4% of total plant electrical energy consumption.

In a study at three industrial facilities, average electrical distribution system losses accounted for 2% of plant annual energy use. Losses due to poor connections represented one-third of these losses and accounted for 40% of the savings after corrective actions were taken.

Inadequate conductor sizing will result in an excessive voltage drop accompanied by increased energy losses and reduced motor torque. The National Electrical Code (NEC) calls for a 3% limit on voltage drop. Increased resistance due to undersized conductors and poor connections converts electrical energy into heat and imposes additional loads on the plant distribution system.

Maintenance of connections is generally referred to as termination maintenance. Termination maintenance is generally a cost-effective electrical distribution system energy savings measure. Causes of poor connections include:

• Loose or corroded cable terminals and bus bar connections

• Poorly crimped connections to conductors

• Loose, worn, or poorly adjusted contacts in motor controllers or circuit breakers

• Loose, dirty, or corroded fuse clips on manual disconnect switches.

Distribution system losses due to poor electrical contacts appear as hot spots caused by increased resistance or electric power (I2R) losses. These hot spots may be detected by infrared thermography or a voltage drop survey. Inexpensive hand-held infrared thermometers can quickly and safely reveal hot spots.

Terminations should be regularly inspected. The cost of replacing fuse clips or cleaning breaker fingers is low compared with the significant energy savings resulting from such measures in addition to the secondary benefits, including less downtime during unsched- uled equipment outages and improved safety due to reduced fire hazards.

Conducting a Voltage Drop Survey A voltage drop survey can usually be done in-house with existing equipment such as a handheld voltmeter. Voltage drop measurements should be taken from the input of each panel to the panel output for each load. For a typical motor circuit, measure the voltage drop from the bus bar to the load side of the motor starter. Compare the magnitude of the voltage drop for each phase with the voltage drop for the other phases supplying the load. A voltage drop difference of more than 15% indicates that testing should be initiated to identify poor circuit connections. Even with good balance, an excessive voltage drop indicates that component voltage drop testing should be initiated. Note that motor efficiencies are determined at rated voltage with balanced phases. Undervoltage operation can result in increased currents, reduced starting torque, and lower efficiency.

### Suggested actions / sidebar

Suggested Actions

• Conduct a voltage drop survey. Voltage drop information can be used to determine energy losses and excess energy consumption due to loose and dirty connections. Voltage drop measurements should be taken at each phase. The voltage drop is simply the voltage difference across the connection. The total energy loss in a three-phase component is determined by summing the losses for each phase. Limit the load on each circuit or install larger-than- code-minimum conductors if the in-plant distribution system voltage drop still exceeds 3%, following termination maintenance.

## Page 2

Example Measurements at a motor control center (MCC) breaker indicate voltage drops of 8.1, 5.9, and 10.6 volts on L, L, and L, respectively. The driven equipment is continuously 1 2 3 operated. Measured line currents are 199.7, 205.7, and 201.8 amps for L, L, and L. 1 2 3 Voltage drop measurements for circuits serving similar loads indicate that a voltage drop of 2.5 volts should be obtainable. The potential annual energy and electrical demand savings from correcting the problem are shown in the table below.

Table 1. Excess Energy Consumption at an MCC Breaker

```text
       Measured Excess                   Excess
                        Current, Excess
Circuit Voltage Voltage                 Energy Use,
                         Amps   Power, kW
      Drop, Volts Drop, Volts           kWh/year
  L      8.1     5.6     199.7    1.12    9,796
  1
  L      5.9     3.4     205.7    0.7      6,126
  2
  L      10.6     8.1    201.8    1.63    14,318
  3
                         Totals: 3.45    30,240
```

Assuming a utility energy charge of $0.08 per kilowatt-hour (kWh) with a demand charge of $8.00 per kilowatt (kW) per month, potential savings are valued at:

Savings = 3.45 kW x $8.00/kW per month x 12 months per year + 30,240 kWh per year x $0.08/kWh = $331 + $2,420 = $2,750 per year (for a single breaker).

### Resources / sidebar

Resources

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
