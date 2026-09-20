---
document_id: "doe-motor-ts12"
title: "Is it Cost-Effective to Replace Old Eddy-Current Drives?"
version: "November 2012"
reviewed_on: "2026-09-18"
teaching_only: false
device_ids: []
product_model: null
sources: ["https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet12.pdf"]
authoring: "Extracted original English, geometric column separation, whitespace normalization; no AI summary or translation"
language: "en"
source_url: "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet12.pdf"
publisher: "U.S. Department of Energy, Advanced Manufacturing Office"
source_document_id: "DOE/GO-102012-3737"
source_pages: ["1", "2"]
applicability: "General industrial motor-system guidance; verify motor design, operating conditions and manufacturer instructions. No mapped project device. Historical publication; not a statement of current standards."
license: "DOE government information public-domain policy; third-party material may be protected. Local study corpus, no assertion of blanket open license."
source_sha256: "4ea1d416b8823d44318b5c740516588b7e7e310760155e01f6ed3db427604fc2"
---

# Is it Cost-Effective to Replace Old Eddy-Current Drives?

## Page 1

Is It Cost-Effective to Replace Old Eddy-Current Drives?

Electronic pulse-width-modulated (PWM) variable frequency drives (VFD) may be cost- effective replacements for aging or high-maintenance eddy-current drives that are used with variable torque loads, such as centrifugal fans or pumps. However, a VFD may not be a suitable replacement for high-torque, repetitive-slip applications, such as a punch press or a crusher. Eddy-current drives can produce more torque at low speed than an induction motor and VFD. When switching to a VFD for a constant torque load, the motor and the drive may require being oversized by a factor of 150% to 200%.

The eddy-current drive or clutch is a slip device consisting of two rotating elements that are coupled by a magnetic field. The slip and rotor speed are determined by the magnetic field strength. An alternating current (AC) motor drives a constant-speed rotating drum that surrounds a cylinder (rotor), which is coupled to an output shaft. Torque is transmitted from the outer rotating drum to the rotor with an adjustable magnetic field. The losses from a slip- based VFD are approximately equal to the amount of slip, or difference between synchronous speed and operating speed, divided by the synchronous speed. The drive efficiency at each operating point is equal to 100% minus the percent losses. Table 1 indicates the efficiency range of a magnetically coupled eddy-current drive when matched to a centrifugal load.

Table 1. Efficiency Versus Speed for an Eddy-Current-Coupled Centrifugal Load1

```text
Drive Speed, % of Full-Load        Eddy-Current Drive
                      Load %
      Speed                          Efficiency, %
       100             100           94.3 to 99.3
       90              72.9          85.9 to 90.4
       80              51.2           76.1 to 80.1
       70              34.3          66.9 to 70.5
       60              21.6          56.9 to 59.8
       50              12.5          47.7 to 50.2
       40              6.4            39.7 to 41.7
       30              2.7           28.6 to 29.9
```

1 Source: Coyote Electronics Inc. “Payback®” Magnetic-Coupled. Variable Speed Drive Literature.

Energy Savings Example

An eddy-current drive on a standard efficiency motor-driven 50-hp boiler forced-draft fan has reached the end of its useful operating life; the proposed replacement is a PWM VFD. The fan operates for 8,000 hours per year while delivering 90% of rated flow for 20% of the time, 80% flow for 50% of the time, and 70% of rated flow for the remaining operating hours. Energy savings are achieved because of the improved efficiency of the PWM drive over the eddy- current drive. The annual energy consumption of the existing system or eddy-current baseline is calculated in Table 2.

As the eddy-current drive efficiency drops rapidly at loads below 70%, energy savings are extremely sensitive to the load profile and duty cycle. Table 3 provides the calculations for the weighted input power for the system, if the existing eddy-current drive is replaced with a VFD. The potential annual energy savings are:

(26.05 – 21.99) kW x 8,000 hrs/year = 32,480 kWh/year.

At an electrical rate of $0.08/kWh, the value of these savings is:

32,480 kWh x $0.08/kWh = $2,600/year.

### Suggested actions / sidebar

Suggested Actions

• Contact your drive supplier to obtain drive efficiency information as a function of motor operating speed or drive power output. Use this information to determine potential energy savings through use of a PWM VFD versus an eddy-current drive.

• When VFD part-load performance values are not readily available, use the values given in Motor Systems Tip Sheet #11, Adjustable Speed Drive Part-Load Efficiency.

• Use the U.S. Department of Energy’s (DOE) MotorMaster+ 4.0 software tool to obtain efficiencies for integral horsepower National Electrical Manufacturers Association (NEMA) Design A and B motors at full- and part-load speeds.

## Page 2

Table 2. Average Power Requirements for a Centrifugal Fan with Eddy-Current Drive Speed Control

```text
          % of            Motor   Eddy-  Weighted
% of Rated      Load, Shaft
        Operating       Efficiency, Current Drive Input Power
Fan Speed         hp
          Time             %    Efficiency, % kW
  90      20      36.4    91.6    90.0    6.59
  80      50      25.6    90.9    80.0    13.13
  70      30      17.2    86.6    70.0    6.33
                                  Total:  26.05
```

Note that the input power (in kW) is equal to 0.746 kW/hp times the shaft horsepower divided by the product of the motor and drive efficiency values. The weighted input power value is the input power times the load duty cycle percentage divided by 100. In Table 3, when the VFD is installed, the fan power requirements decrease.

Table 3. Average Power Requirements for a Centrifugal Fan with VFD Speed Control

```text
          % of            Motor   VFD    Weighted
% of Rated      Load, Shaft
        Operating       Efficiency, Efficiency, Input Power
Fan Speed         hp
          Time             %       %       kW
  90      20      36.45   91.6     96     6.18
  80      50      25.6    90.9     95     11.05
  70      30      17.2    86.6     93     4.76
                                  Total:  21.99
```

Additional energy savings could be obtained by replacing the old standard efficiency motor with a premium efficiency model. See Motor Systems Tip Sheet #1, When to Purchase Premium Efficiency Motors.

Although early replacement of an older eddy-current drive with a VFD might not meet the two-year simple payback often required by industry, the cost effectiveness of this replacement can be significantly improved if a utility efficiency incentive is available. Other factors that could favor replacement include predictive maintenance tests that indicate an impending failure, lack of availability of replacement parts, or eddy-current failure that requires repair.

Load Considerations

Eddy-current drives are not directly coupled to the load shaft, so they do not transmit vibrations from the driven-equipment to the motor and provide inherent protection against load seizures. However, installers must always ensure that operational problems are not created through installation of a VFD. For some installations, these potential issues outweigh the potential cost savings from replacing old eddy-current drives.

Before replacing existing eddy-currents drives, consider whether the selected VFDs meet criteria inherent to eddy-current drives, such as:

• Can be used with standard efficiency motors

• Produce no harmonic distortion

• Avoid nuisance trips when power disturbances occur

• Operate independently of the motor power supply voltage.

For more information, please refer to Motor Systems Tip Sheet #15, Minimize Adverse Motor and Adjustable Speed Drive Interactions.

### Resources / sidebar

Resources

National Electrical Manufacturers Association (NEMA)—Visit www.nema.org for information on motor standards, application guides, and technical papers.

U.S. Department of Energy (DOE)— For more information on motor and motor-driven system efficiency and to download the MotorMaster+ software tool, visit the Advanced Manufacturing Office (AMO) website at manufacturing.energy.gov.
