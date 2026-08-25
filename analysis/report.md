# AM5 board verdicts from Buildzoid's claims

Derived from `data/claims.jsonl` (2,736 claims, Stage B output), board
names resolved per-claim by 28 Opus 5 workers, graded by: how he knows
it (tested > reasoned > secondhand; warning = strong negative), subject
(voltage/firmware safety and VRM capacity weighted highest), CPU power
draw for transferred evidence, recency, and resolution confidence.

**Read this before trusting it:**
- Scores RANK evidence density and direction. They are not his verdicts.
  The claims and links are the product; the score is the sort order (V8, V14).
- Category/polarity labels come from Stage B extraction and can be wrong
  on garbled captions. Every claim carries its link — check before buying (V11).
- A board missing here means he did not cover it, not that it is bad (V12).
- Evidence from a non-16-core CPU is transferred, and labeled with the
  CPU when the row names one (V9).

## Ranking (safety-weighted)

| # | Board | Safety | Safety claims | Warnings | Total |
|---|-------|--------|---------------|----------|-------|
| 1 | ASUS X670E PROART | +70.6 | 27 | 0 | 74 |
| 2 | ASUS X670E CROSSHAIR GENE | +35.8 | 17 | 1 | 51 |
| 3 | GIGABYTE X670 AORUS ELITE | +32.3 | 12 | 0 | 39 |
| 4 | ASUS B650E STRIX F | +29.1 | 23 | 0 | 50 |
| 5 | MSI B850 EDGE (ITX) | +21.5 | 15 | 0 | 24 |
| 6 | ASROCK B650 HDV | +16.6 | 10 | 0 | 72 |
| 7 | MSI X870 TOMAHAWK | +15.9 | 38 | 0 | 112 |
| 8 | ASUS X870 STRIX I (ITX) | +12.9 | 19 | 0 | 47 |
| 9 | GIGABYTE X870 AORUS ELITE | +12.4 | 3 | 0 | 19 |
| 10 | GIGABYTE X670E AORUS XTREME | +9.9 | 7 | 0 | 31 |
| 11 | ASUS X870 STRIX (ITX) | +7.6 | 2 | 0 | 3 |
| 12 | GIGABYTE B650E AORUS MASTER | +6.1 | 19 | 0 | 64 |
| 13 | ASROCK X670E STEEL LEGEND | +5.0 | 3 | 0 | 12 |
| 14 | ASROCK B650 | +4.8 | 3 | 0 | 11 |
| 15 | MSI X670E | +4.2 | 2 | 0 | 21 |
| 67 | ASROCK B650 STEEL LEGEND | -5.4 | 2 | 0 | 2 |
| 68 | GIGABYTE B650E | -5.7 | 1 | 0 | 14 |
| 69 | ASROCK B650 LIVEMIXER | -8.2 | 22 | 0 | 73 |
| 70 | GIGABYTE B650 AORUS ELITE | -9.8 | 5 | 0 | 16 |
| 71 | GIGABYTE X670 AORUS MASTER | -14.9 | 6 | 0 | 18 |
| 72 | ASROCK X870E TAICHI | -19.2 | 13 | 1 | 44 |
| 73 | MSI B650 EDGE (ITX) | -23.8 | 14 | 3 | 45 |
| 74 | GIGABYTE X670E AORUS MASTER | -38.4 | 18 | 9 | 35 |
| 75 | GIGABYTE B850 FORCE | -39.2 | 12 | 0 | 31 |


# Availability check (tweakers.net Pricewatch, 2026-08-25)

| Board | Safety | Lowest price | Sellers | Status |
|---|---|---|---|---|
| ASUS ProArt X670E-Creator WiFi | +70.6 | — | 0 | discontinued |
| ASUS ROG Crosshair X670E Gene | +35.8 | — | 0 | discontinued |
| Gigabyte X670 Aorus Elite AX | +32.3 | EUR 149.95 | 1 | almost gone |
| ASUS ROG Strix B650E-F Gaming WiFi | +29.1 | EUR 189 | 3 | available, 11% price drop |
| MSI MPG B850I Edge Ti WiFi (ITX) | +21.5 | EUR 259.18 | 9 | available |
| ASRock B650M-HDV/M.2 | +16.6 | EUR 79 | 17 | available, 18% price drop |
| MSI MAG X870 Tomahawk WiFi | +15.9 | EUR 289 | 6 | available |
| ASUS ROG Strix X870-I Gaming WiFi (ITX) | +12.9 | EUR 394 | 23 | available |
| Gigabyte X870 Aorus Elite WiFi7 | +12.4 | EUR 239 | 22+ | available |
| Gigabyte X670E Aorus Xtreme | +9.9 | — | 0 | discontinued |
| Gigabyte B650E Aorus Master | +6.1 | — | 0 | discontinued |
| ASRock X670E Steel Legend | +5.0 | — | 0 | discontinued |

Note: the MSI MAG X870E Tomahawk (EUR 297, 18 sellers) is a DIFFERENT board
from the X870 Tomahawk the evidence covers. No claim in the store names the
X870E variant; buying it on this evidence would be a transfer he never made.

# The five to consider

## 1. ASUS X670E PROART

Safety score +70.6 from 27 safety claims (0 warnings), 74 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "level two is already such insane amounts of vop especially compared to most other am5 motherboards which max out at like maybe 80ish molts of V droop this has like a 200 molts more V Dro available than uh other boards"
  [https://youtu.be/h1b69qEe7NQ?t=540](https://youtu.be/h1b69qEe7NQ?t=540)
- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "800 khz switching frequency on this motherboard actually delivers the best voltage regulation which is pretty interesting to me"
  [https://youtu.be/h1b69qEe7NQ?t=760](https://youtu.be/h1b69qEe7NQ?t=760)
- **tested / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "level 8 LLC is of course a voltage regulation disaster but not the worst thing I've ever measured"
  [https://youtu.be/h1b69qEe7NQ?t=1240](https://youtu.be/h1b69qEe7NQ?t=1240)
- **tested / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the worst case scenario undershoot was about 90 molts at 1.16 volts"
  [https://youtu.be/h1b69qEe7NQ?t=1290](https://youtu.be/h1b69qEe7NQ?t=1290)
- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "now our average undershoot is about 40 molts which is actually really good"
  [https://youtu.be/h1b69qEe7NQ?t=1690](https://youtu.be/h1b69qEe7NQ?t=1690)

**Watch these (densest for this board):**

- [Motherboard PCB Breakdown: ASUS Pro ART X670E Creator Wifi](https://youtu.be/HoTzIK6zifw) (weight 52.8)
- [ASUS ProArt X670E CREATOR WIFI Vcore LLC settings deep dive](https://youtu.be/h1b69qEe7NQ) (weight 31.0)
- [2x16GB 6200 CL26 with Ryzen on an ASUS ProART X670E Creator](https://youtu.be/QJKBPJQVIZA) (weight 7.8)

## 2. ASUS X670E CROSSHAIR GENE

Safety score +35.8 from 17 safety claims (1 warnings), 51 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "but like in terms of like voltage regulation it's the best board I ever measured"
  [https://youtu.be/-VUqaRgpEro?t=6060](https://youtu.be/-VUqaRgpEro?t=6060)
- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the one motherboard that I've measured that has the option not to like have these like under like not have undershoot uh is the Crosshair x670 e Gene"
  [https://youtu.be/3m1gNZfdSi0?t=1130](https://youtu.be/3m1gNZfdSi0?t=1130)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "I've already measured the voltage regulation performance of this board it is very good in fact it's the best motherboard I've measured so far"
  [https://youtu.be/YxuzeDO0_90?t=2260](https://youtu.be/YxuzeDO0_90?t=2260)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the total bulk capacitance on the v-core vrm of this motherboard is is like nothing um but the voltage regulation is actually really really good"
  [https://youtu.be/YxuzeDO0_90?t=2330](https://youtu.be/YxuzeDO0_90?t=2330)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the only am5 motherboard I've tested where you had like the option to set the V droops so high that there wasn't any more undershoot like unnecessarily high levels of edroup uh was the Crosshair x670 Gene"
  [https://youtu.be/k1rFRuaCChU?t=700](https://youtu.be/k1rFRuaCChU?t=700)

**Watch these (densest for this board):**

- [mobo PCB Breakdown: ASUS Crosshair X670E Gene](https://youtu.be/YxuzeDO0_90) (weight 34.8)
- [End of 2023 motherboard discussion stream](https://youtu.be/-VUqaRgpEro) (weight 10.2)
- [Ultra 7 270K and MSI Z890 Tomahawk test/bench stream](https://youtu.be/MJP_DQpeIKg) (weight 3.0)

## 3. GIGABYTE X670 AORUS ELITE

Safety score +32.3 from 12 safety claims (0 warnings), 39 claims total.

**Top safety evidence:**

- **tested / vrm_capacity / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the board literally doesn't need a heatsink um as demonstrated by me running it without a heatsink in Prime 95 and the hot hottest part of the vrm ended up at like 75 degrees Celsius"
  [https://youtu.be/EGR2dA25a5o?t=1860](https://youtu.be/EGR2dA25a5o?t=1860)
- **tested / vrm_capacity / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "you can get like the x670 aorus elite and that also has no issues powering a 7950x prime 95 small ffts static overclock with no vrm heatsink it can do it"
  [https://youtu.be/nAFqGdqRNQ8?t=1780](https://youtu.be/nAFqGdqRNQ8?t=1780)
- **tested / vrm_capacity / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the vrm with you know no heatsink installed whatsoever and no real airflow has been sitting at 100 at a 75 77 degrees Celsius um so yeah you'd like the vrm on this board is incredibly Overkill"
  [https://youtu.be/7wRn1bkqXNA?t=230](https://youtu.be/7wRn1bkqXNA?t=230)
- **tested / vrm_capacity / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "here we have 16 V Core Power stages there's 70 amp power stages from Infineon no vrm heatsink this has no issues powering a 7950x"
  [https://youtu.be/7wRn1bkqXNA?t=460](https://youtu.be/7wRn1bkqXNA?t=460)
- **reasoned / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "in terms of physical aspects I don't really see anything to complain about like anything that would directly lead to bad voltage regulation I've not yet measured the board with an oscilloscope"
  [https://youtu.be/EGR2dA25a5o?t=2420](https://youtu.be/EGR2dA25a5o?t=2420)

**Watch these (densest for this board):**

- [mobo PCB Breakdown: X670 Aorus Elite AX](https://youtu.be/EGR2dA25a5o) (weight 31.2)
- [Most X670 motherboard VRMs are MASSIVE OVERKILL](https://youtu.be/7wRn1bkqXNA) (weight 7.0)
- [Ranting about X870 VRM/power stage current ratings AGAIN](https://youtu.be/Nd-bSs4HuMM) (weight 2.5)

## 4. ASUS B650E STRIX F

Safety score +29.1 from 23 safety claims (0 warnings), 50 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "there is a switching frequency setting I tried messing around with it in like pre-testing for this video it doesn't do anything"
  [https://youtu.be/MbHVSX1GulI?t=300](https://youtu.be/MbHVSX1GulI?t=300)
- **tested / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "this board seems to float around quite a bit like our current average voltage which it some of that's tied to the temperature"
  [https://youtu.be/MbHVSX1GulI?t=620](https://youtu.be/MbHVSX1GulI?t=620)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "so we've got about 50 millivolts of of undershoot um which off the top of my head is slightly better than the ASRock b650 live mixer board"
  [https://youtu.be/MbHVSX1GulI?t=880](https://youtu.be/MbHVSX1GulI?t=880)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the voltage regulation doesn't really change as you increase the LLC setting"
  [https://youtu.be/MbHVSX1GulI?t=920](https://youtu.be/MbHVSX1GulI?t=920)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "yeah so 50 millivolts of undershoot that's not that's not a bad result by like with from my experience with am5 motherboards so far"
  [https://youtu.be/MbHVSX1GulI?t=960](https://youtu.be/MbHVSX1GulI?t=960)

**Watch these (densest for this board):**

- [mobo PCB Breakdown: ASUS Strix B650E-F Gaming WIFI](https://youtu.be/MJAehA5_wHs) (weight 45.8)
- [ASUS Strix B650E-F Gaming wifi voltage regulation and LLC testing](https://youtu.be/MbHVSX1GulI) (weight 27.0)
- [End of 2023 motherboard discussion stream](https://youtu.be/-VUqaRgpEro) (weight 3.5)

## 5. MSI B850 EDGE (ITX)

Safety score +21.5 from 15 safety claims (0 warnings), 24 claims total.

**Top safety evidence:**

- **tested / vrm_capacity / negative** (2026-01-26, CPU not named (transferred evidence, unspecified AM5))
  > "200 amps output current, and the VRM heat sink, uh, well, the VRM MOSFET temperature, the external reading hit 110 degrees. the internal reading hit 119 degrees Celsius"
  [https://youtu.be/SZ9PWa2Ea7w?t=1290](https://youtu.be/SZ9PWa2Ea7w?t=1290)
- **tested / vrm_capacity / positive** (2026-01-26, CPU not named (transferred evidence, unspecified AM5))
  > "with some direct air flow pointed at the motherboard, the VRM maxed out at 90° C external temperature and 99° C internal"
  [https://youtu.be/SZ9PWa2Ea7w?t=1380](https://youtu.be/SZ9PWa2Ea7w?t=1380)
- **tested / vrm_capacity / positive** (2026-01-26, CPU not named (transferred evidence, unspecified AM5))
  > "1600 RPM fan pulling the VRM down to 90° C. I consider that like a success"
  [https://youtu.be/SZ9PWa2Ea7w?t=1450](https://youtu.be/SZ9PWa2Ea7w?t=1450)
- **tested / vrm_capacity / positive** (2026-01-26, CPU not named (transferred evidence, unspecified AM5))
  > "I am a fan of the fact that this has a Vcore VRM that doesn't completely face plant when you try to overclock a 9950X on this board"
  [https://youtu.be/SZ9PWa2Ea7w?t=1960](https://youtu.be/SZ9PWa2Ea7w?t=1960)
- **reasoned / voltage_firmware_safety / positive** (2026-01-26, CPU not named (transferred evidence, unspecified AM5))
  > "I would expect this motherboard's voltage regulation to be really, really good because of these"
  [https://youtu.be/SZ9PWa2Ea7w?t=1700](https://youtu.be/SZ9PWa2Ea7w?t=1700)

**Watch these (densest for this board):**

- [mobo PCB Breakdown: MSI MPG B850i Edge Ti Wifi](https://youtu.be/SZ9PWa2Ea7w) (weight 44.0)

# Boards his evidence argues against

## AVOID:. GIGABYTE X670 AORUS MASTER

Safety score -14.9 from 6 safety claims (0 warnings), 18 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / negative** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "once it's broken you need to clear seos and literally set everything up again and there's like a specific procedure you have to go through in order for it to not break and it's just a massive pain"
  [https://youtu.be/idREuMs6gE0?t=8630](https://youtu.be/idREuMs6gE0?t=8630)
- **tested / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "it's set to 1.15 volts with standard LLC which is the highest v-true policy that this motherboard has honestly I wish there was an even droopier option because looking at the oscilloscope we can very clearly see that the"
  [https://youtu.be/k1rFRuaCChU?t=120](https://youtu.be/k1rFRuaCChU?t=120)
- **reasoned / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "I wouldn't recommend an x670 Master for eclk because gigabyte keeps randomly breaking it like on some bios versions it works at some bios versions it doesn't"
  [https://youtu.be/5L7oEKZJVUU?t=13660](https://youtu.be/5L7oEKZJVUU?t=13660)
- **tested / vrm_capacity / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "gigabytes arguably overly aggressive vrm tuning is not really the main focus of this video"
  [https://youtu.be/k1rFRuaCChU?t=150](https://youtu.be/k1rFRuaCChU?t=150)
- **tested / voltage_firmware_safety / mixed** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "our average voltage and the scope is hooked up to the back of the board is around 1.156 volts and our minimums are low bottoming out at around 1.1 volt so there's like 50 ish millivolts of undershoot which is pretty well"
  [https://youtu.be/k1rFRuaCChU?t=330](https://youtu.be/k1rFRuaCChU?t=330)

**Watch these (densest for this board):**

- [A demonstration of why Vdroop is good with the Ryzen 9 7950X.](https://youtu.be/k1rFRuaCChU) (weight 8.5)
- [END OF YEAR BUILDZOID GAMING STREAM](https://youtu.be/MOeh9TCnYaE) (weight 5.2)
- [Reacting to RAM timings ep14](https://youtu.be/idREuMs6gE0) (weight 3.8)

## AVOID:. ASROCK X870E TAICHI

Safety score -19.2 from 13 safety claims (1 warnings), 44 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / positive** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "ack is the first manufacturer I've seen to just set the S so voltage straight to 1.3 Vols when you turn Expo on um they set it to 1.2"
  [https://youtu.be/JRicT-6CiM8?t=700](https://youtu.be/JRicT-6CiM8?t=700)
- **tested / voltage_firmware_safety / negative** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "so voltage I'm at 1.24 this is more than this CPU should need but after my experience with that 9800x 3D I didn't want to take any chances so morec voltage uh more safety margin like the like I would like if we were on a"
  [https://youtu.be/UzFZNvUYzE8?t=1150](https://youtu.be/UzFZNvUYzE8?t=1150)
- **tested / voltage_firmware_safety / negative** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "I I really suspect that the taite just like under reports voltage or the tomahawk over reports"
  [https://youtu.be/fy6zjINUQuc?t=1085](https://youtu.be/fy6zjINUQuc?t=1085)
- **tested / voltage_firmware_safety / negative** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "I did try using uh override mode on the taichi uh but enabling that on the taichi is is a mess and so I just gave up on that at some point"
  [https://youtu.be/fy6zjINUQuc?t=1310](https://youtu.be/fy6zjINUQuc?t=1310)
- **tested / vrm_capacity / positive** (2025-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "now both of these results are quite good um like 40 molts average undershoot is a good result as far as I'm concerned"
  [https://youtu.be/fy6zjINUQuc?t=1265](https://youtu.be/fy6zjINUQuc?t=1265)

**Watch these (densest for this board):**

- [Why I bought an Asrock X870E Taichi Lite](https://youtu.be/fy6zjINUQuc) (weight 21.5)
- [G.skill 2x24GB DDR5-8000 CL40 EXPO optimized timings on Asrock X870E Taichi Lite](https://youtu.be/JRicT-6CiM8) (weight 11.2)
- [2x24GB DDR5-6400 CL28 // Ryzen 9 9950X // Asrock X870E Taichi Lite](https://youtu.be/UzFZNvUYzE8) (weight 10.8)

## AVOID:. MSI B650 EDGE (ITX)

Safety score -23.8 from 14 safety claims (3 warnings), 45 claims total.

**Top safety evidence:**

- **warning / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "the loadline calibration settings on this board well one of them has issues so mode one should never ever be used okay it is really bad"
  [https://youtu.be/3m1gNZfdSi0?t=389](https://youtu.be/3m1gNZfdSi0?t=389)
- **tested / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "first of all you don't want to use the override mode it's like it breaks a whole B well it breaks all of your temperature monitoring and power monitoring and it it breaks a whole bunch of stuff"
  [https://youtu.be/3m1gNZfdSi0?t=455](https://youtu.be/3m1gNZfdSi0?t=455)
- **tested / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "it has like a weird 1.3 volt core voltage limit so if you're trying to push High voltages also doesn't work for that"
  [https://youtu.be/3m1gNZfdSi0?t=470](https://youtu.be/3m1gNZfdSi0?t=470)
- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "it didn't do anything weird at 1,000 khz which is better than some of the other motherboards I've tested"
  [https://youtu.be/3m1gNZfdSi0?t=552](https://youtu.be/3m1gNZfdSi0?t=552)
- **tested / voltage_firmware_safety / negative** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "now mode one is a complete disaster in terms of voltage regulation because it doesn't uh like yeah it removes all of the V Dro"
  [https://youtu.be/3m1gNZfdSi0?t=1520](https://youtu.be/3m1gNZfdSi0?t=1520)

**Watch these (densest for this board):**

- [MSI B650i EDGE WIFI Vcore load line calibration testing // mode1 is BIG OOF](https://youtu.be/3m1gNZfdSi0) (weight 31.5)
- [Rambling about MSI's AM5 motherboards.](https://youtu.be/dJWu7BQ5uGQ) (weight 12.2)
- [MSI B650i EDGE Wifi RAM overclocking. 2x32GB 6200 30-37-35-40 1.43V](https://youtu.be/5q04Svi1CNg) (weight 10.2)

## AVOID:. GIGABYTE X670E AORUS MASTER

Safety score -38.4 from 18 safety claims (9 warnings), 35 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / positive** (2024-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "it seems to be like fixed on the f30 bi"
  [https://youtu.be/pKhyVR4rtxI?t=3450](https://youtu.be/pKhyVR4rtxI?t=3450)
- **tested / voltage_firmware_safety / positive** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "luckily just turning on Expo doesn't do anything particularly stupid um the soc voltages you can see it measured over here"
  [https://youtu.be/O2n4rOWehtQ?t=120](https://youtu.be/O2n4rOWehtQ?t=120)
- **warning / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "you know I have my SOC voltage set to 1.2 volts but as we can see it is not actually 1.2 volts it's 1.25 volts"
  [https://youtu.be/O2n4rOWehtQ?t=260](https://youtu.be/O2n4rOWehtQ?t=260)
- **warning / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "so this already is like in my opinion not acceptable you should not have uh uh settings in your bios that don't do what you would think they do"
  [https://youtu.be/O2n4rOWehtQ?t=300](https://youtu.be/O2n4rOWehtQ?t=300)
- **warning / voltage_firmware_safety / negative** (2023-08-26, CPU not named (transferred evidence, unspecified AM5))
  > "gigabyte seems to have like an auto SOC voltage rule that for some reason latches onto the freaking vdd voltage of all things"
  [https://youtu.be/O2n4rOWehtQ?t=560](https://youtu.be/O2n4rOWehtQ?t=560)

**Watch these (densest for this board):**

- [Testing some very strange VSOC behaviour on the Gigabyte X670E Aorus Master with the F10c BIOS](https://youtu.be/O2n4rOWehtQ) (weight 38.2)
- [Rambling about Gigabyte's AM5 motherboard lineup](https://youtu.be/uB-wXLb_08o) (weight 13.8)
- [Rambling about my 7800X3D and 4070Ti daily system.](https://youtu.be/pKhyVR4rtxI) (weight 9.2)

## AVOID:. GIGABYTE B850 FORCE

Safety score -39.2 from 12 safety claims (0 warnings), 31 claims total.

**Top safety evidence:**

- **tested / voltage_firmware_safety / negative** (2025-12-26, CPU not named (transferred evidence, unspecified AM5))
  > "the actual voltage regulation here is um, well, it's not like the worst thing I've ever measured, but it's also not good. Um, and the worst part is is the board has like eight different load line calibration settings and"
  [https://youtu.be/_EUeMsN6rsQ?t=2290](https://youtu.be/_EUeMsN6rsQ?t=2290)
- **tested / voltage_firmware_safety / negative** (2025-12-26, CPU not named (transferred evidence, unspecified AM5))
  > "the load line calibration settings on this board basically fit between the level eight LLC on a Crosshair X870E Hero and the level seven LLC. Which yeah, that sort of explains why the voltage regulation is so bad"
  [https://youtu.be/_EUeMsN6rsQ?t=2340](https://youtu.be/_EUeMsN6rsQ?t=2340)
- **tested / vrm_capacity / negative** (2025-12-26, CPU not named (transferred evidence, unspecified AM5))
  > "I have actually uh done some VRM thermal testing with this board and the results do not match the theoretical expectations. And I can think of a pretty simple explanation for why that happens. It's the six-layer PCB"
  [https://youtu.be/_EUeMsN6rsQ?t=1450](https://youtu.be/_EUeMsN6rsQ?t=1450)
- **tested / vrm_capacity / negative** (2025-12-26, CPU not named (transferred evidence, unspecified AM5))
  > "This board won't passively run even a stock 9950X in Prime95"
  [https://youtu.be/_EUeMsN6rsQ?t=1500](https://youtu.be/_EUeMsN6rsQ?t=1500)
- **tested / vrm_capacity / negative** (2025-12-26, CPU not named (transferred evidence, unspecified AM5))
  > "without direct air flow over the VRM section of the board, the VRM will hit 115° C and immediately start like well, not immediately, but like after a couple minutes it'll uh thermal throttle like it'll throttle the CPU"
  [https://youtu.be/_EUeMsN6rsQ?t=1560](https://youtu.be/_EUeMsN6rsQ?t=1560)

**Watch these (densest for this board):**

- [mobo PCB Breakdown: Gigabyte B850M Force](https://youtu.be/_EUeMsN6rsQ) (weight 35.8)
- [DDR5-8300 CL36 with a Ryzen 7 9700X and Gigabyte B850M Force](https://youtu.be/96s9FOBQVPI) (weight 7.0)
