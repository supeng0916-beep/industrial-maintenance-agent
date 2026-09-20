---
document_id: "doe-motor-ts10"
title: "Turn Motors Off When Not in Use"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet10.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet10.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3742"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "c25530d8daf61b12e91af44dc100931aaf55deab1e3d986489d6fa7127e18d47"
---

# Turn Motors Off When Not in Use

## Page 1

Turn Motors Off When Not in Use

Motors do not use energy when turned off. Reducing motor operating time by just 10% usually saves more energy than replacing a standard efficiency motor with a premium efficiency motor. In fact, given that more than 97%1 of the life cycle cost of purchasing and operating a motor in a typical installation is energy related, turning a motor off 10% of the time could reduce energy costs enough to purchase several new motors.

However, a belief persists that stopping and starting motors is harmful. Many users believe that repeated motor starts will use more energy than constant operation, increase utility demand charges, and shorten motor life. While these opinions are not completely without basis, they do need to be put into proper perspective.

During starting, a motor accelerates and draws more power than when it is operating steadily at full load. While a typical National Electrical Manufacturers Association (NEMA) Design B motor may draw from four to eight times the full-load current during starting, the power factor is low so the input power is not four to eight times the rated load power. Starting usually takes less than 2 seconds and rarely exceeds 10 seconds, even for large, high-inertia loads. Just one minute of additional running time consumes far more energy than a motor starting event.

Another motor starting concern involves increased utility demand charges. Again, the excess starting demand is small due to the short duration of the motor starting interval. Peak monthly demand charges are generally based on a facility’s average energy use over a fixed or rolling average window of 15 to 60 minutes in duration. Only when start- ing large or large groups of motors at once should the user be concerned with peak demand charges. Check with your utility to determine how it assesses peak demand charges.

Starting Stresses Starting stresses a motor by:

• Applying higher than rated full-load torque to the shaft during acceleration

• Applying high magnetic forces to the rotor cage and winding end turns

• Heating the stator winding and the rotor cage. Frequent torque shocks from starting could shorten shaft life through metal fatigue. However, most shaft failures are attributed to bearing failures, excessive belt tension, misapplication, or creep during storage (large motors). Overheating the stator winding and the rotor cage occurs if the hourly number of starts exceeds the NEMA recommendations or the duration of rest time between starts is less than the NEMA allowable value. Heat from exceeding these limits can degrade winding insulation and cause thermal stressing of the rotor cage, leading to cracks and failed end-ring connections.

Repeated Motor Starts and Stops While it is true that starting stresses a motor, motors are designed to be started. For example, motors in applications such as lift pumps or irrigation wells start and stop quite frequently, while obtaining service lives of 15 years or more. As long as the frequency of starts given in NEMA MG 10-2001, Revision 2007, is not exceeded, motor lifetime is not significantly affected.

NEMA provides standards for starting duty which consider inertia of the load—an important factor in starting stress. NEMA also provides guidance relating to start-run- stop-rest cycles that are often employed in energy management programs.

### Suggested actions / sidebar

Suggested Actions

• Keep track of your motors through a motor system management plan. Consider times when motors can be shut down, including shift changes, lunch breaks, or during process interruptions.

• Energy saving opportunities often exist when motors drive loads in parallel, such as compressors or pumps. Evaluate sequencing of these motors.

• Install automatic shutdown timers so motors will be turned off when they would otherwise be running idle or unloaded for intervals longer than the rest intervals identified in NEMA MG 10-2001, Revision 2007.

• Shut down equipment that is energized but not in use for periods of time longer than NEMA recommendations for start-run-stop-rest cycles.

• Consider adjustable speed drives, soft starters, wye-delta starting, or autotransformers to reduce starting stresses on equipment that requires frequent starting and stopping.

## Page 2

Frequent stopping and starting, even within NEMA limits, does stress a motor due to mechanical flexing of the coils and rotor overheating during acceleration, but there is no known relationship between number of motor starts and normal motor life expectancy. Each start is one factor in the life expectancy and reliability of the motor, and some reduction in life expectancy and reliability must be accepted when a motor is continuously applied at the upper range of its starting duty.

Frequent starting imposes thermal stresses on the motor. Other factors also contribute to temperature rise. When operating in the upper range of starting duty, take these steps to ensure that you are well within tolerances on other sources of thermal stress:

• Keep the motor clean so airflow and heat transfer are not impeded

• Allow sufficient rest time between starts for the heat buildup to dissipate (as given in NEMA MG 10-2001, Revision 2007)

• Keep supply voltage nominal, avoiding voltage unbalance, undervoltage, and harmonics

• Do not overload the motor

• De-rate any motor used in severe ambient environments, such as above 3,000 feet altitude or above 40°C

• Consider continuous monitoring of motor operating conditions with ISA100-compliant wireless sensor networks. You may find that you can substantially increase the time your motors are shut down without approaching the NEMA MG 10-2001, Revision 2007, starting duty limits. For frequent start-stop applications, special motor system designs or an adjustable speed drive might be required, or a clutch/brake may be employed with a constant speed motor. In some applications, servo motors may be specified.

References 1“Electrical Efficiency: Spec the Right Motor and Drive for Lifecycle Performance”, John Malinowski, Baldor Electric Company, November, 2011.

Additional Information

• NEMA MG 1-2011. It provides a table on the maximum inertia load for starting induction motors of various ratings. Motors driving loads that do not exceed these inertia limits can be started twice in immediate succession when the motor is initially at ambient temperature.

• NEMA MG 10-2001, Revision 2007. See Table 7, which provides the maximum number of allowable starts per hour for motors of various horsepower and synchro- nous speed ratings. The table indicates how frequently motors can be started with a rest period between starts and provides a minimum duration for that rest period.

• For information on wireless sensing technology uses, refer to the U.S. Department of Energy’s (DOE) Ways of Using Wireless Technology to Help You Reduce Energy Usage at Your Facility. and Nissan North America: How Sub-Metering Changed the Way a Plant Does Business.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www. nema.org for more information. When making the decision to stop a motor, refer to NEMA MG 10- 2001 Energy Management Guide for Selection and Use of Fixed Frequency Medium AC Squirrel- Cage Polyphase Induction Motors. For large induction motors, refer to NEMA MG 1-2011 Motors and Generators Part 20.12.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
