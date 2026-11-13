# ASTRAN

ASTRAN is an acronym for __Automatic Synthesis of Transistor Networks__. It is a free, open source, physical synthesis framework for Mac and Linux, developed in the microelectronics group (GME) of the Universidade Federal do Rio Grande do Sul (UFRGS), with financial support from CAPES.

It supports automatic layout generation of CMOS cells from a transistor level netlist description in SPICE format. Area overhead compared to high quality hand-made standard-cells layouts is 3.7% on average.
Its functionality is being extended to produce complete circuit layouts. Features include transistor sizing, floorplanning, cell placement, and routing. The framework is very modular and new contributions to this project are welcome.

![Astran](https://github.com/aziesemer/astran/blob/master/Astran/misc/screenshot2.png?raw=true)

### Features:
- ASTRAN 3 is under active development and supports 45+nm technology rules (including freePDK45) like: redundant diff contacts, conditional design rules (metal/poly/diff enclosure of contacts, gate extension on diff, diff to gate spacing, metal/poly spacing on dense line-ends), minimum area,...
- It generates all kinds of logic cells, including non-complementary as PTL;
- Cell instances can be individually sized before generation to reduce delay;
- Cell layout generation flow includes: transistor folding, 1-D transistor placement (using Threshold Accepting metaheuristic), intracell routing (using pathfinder and iterated 1-steiner algorithms) and 2-D layout compaction (using ILP);
- Layouts can be saved in CIF, GDSII and LEF formats. It can also be exported to Cadence ICFB and loaded into Virtuoso;
- Structural Verilog is supported once you provide a Spice description of each cell;
- Includes a command line interpreter for increased flexibility, like the ability to run scripts;

### Requirements:
- C++ compiler with support to C++11;
- Gurobi 5 (it has issues with newer versions, sometimes unfeasible solutions as obtained). It seems that is working normally again with Gurobi 9, according to some feedback. I did not have time to test it, but you may give it a try if you cannot find Gurobi 5.

There is a <a href="https://www.youtube.com/watch?v=IFbCDSMi_FE">video</a> tutorial that can be usefull.
Any question about the tool, please, send me an email: amziesemerj (at) inf.ufrgs.br

If you are using ASTRAN, please cite: <a href="https://www.researchgate.net/publication/262876168_Simultaneous_Two-Dimensional_Cell_Layout_Compaction_Using_MILP_with_ASTRAN?ev=prf_pub">ISVLSI'14</a> or visit my <a href="https://www.researchgate.net/profile/Adriel_Ziesemer_Jr">profile</a>  for other works.

## Building

- On Linux 

The following procedure was tested in Centos 5.11 and Ubuntu 14.04
```
git clone https://github.com/aziesemer/astran.git astran
cd astran/Astran
make
```

- On Mac OSX

Read the INSTALL.txt file.

## Environment (optional)

```ASTRAN_PATH``` needs to point to the astran path.

## Using

- On Command Line

```$Astran --shell```

- On GUI 

![Astran GUI](https://github.com/aziesemer/astran/blob/master/Astran/misc/astran.jpg?raw=true)

## Open PDKs

Astran can generate cells in open PDKs through per-PDK adapters in `pdks/`: SkyWater sky130
(`pdks/sky130/`, compared against `sky130_fd_sc_hd`) and GlobalFoundries gf180mcuD (`pdks/gf180/`, compared
against `gf180mcu_fd_sc_mcu7t5v0`).

```
nix develop                              # librelane EDA tools, HiGHS, g++, pytest
make -C Astran -f cli.mk                 # wx-free command-line build: Astran/build/bin/astran-cli
python3 astran_pdk.py sky130             # inv, nand2, nor2, a21oi: DRC alone and abutted, LVS, area
python3 astran_pdk.py sky130 nand2 --out out/mine
python3 astran_pdk.py gf180              # inv, nand2, nor2, aoi21 against the 7t library
```

The sky130A PDK is looked up in `$ASTRAN_SKY130_DIR`, then `${PDK_ROOT:-~/.ciel}/sky130A`, then the ciel
version pinned in `pdks/sky130/pdk.py`. Intermediate files and reports are kept under `out/sky130/<cell>/`.
Exit status is 0 only if every cell passes; 2 if the environment is unusable. Result of the default run:

```
cell   gen  drc   drc-abut  lvs   w×h          ref w×h      area   ref area  ratio
inv    ok   pass  pass      pass  1.020×3.400  1.380×2.720  3.468  3.754     0.92
nand2  ok   pass  pass      pass  1.700×3.400  1.380×2.720  5.780  3.754     1.54
nor2   ok   pass  pass      pass  1.700×3.400  1.380×2.720  5.780  3.754     1.54
a21oi  ok   pass  pass      pass  2.380×3.400  1.840×2.720  8.092  5.005     1.62
```

The Astran cells carry their own well taps and are 3.4 um tall (not drop-in with hd, which is
2.72 um tall and tapless), so the ratio is pessimistic for Astran. See `pdks/sky130/README.md`
for the details and `pdks/README.md` for how to add a PDK.

The gf180 adapter fetches its PDK with `ciel enable --pdk-family gf180mcu 0fe599b2afb6708d281543108caf8310912f54af`
and generates tapless cells like the 7t library (DRC runs with the library tap cell at the row ends):

```
cell   gen  drc   drc-abut  lvs   w×h          ref w×h      area    ref area  ratio
inv    ok   pass  pass      pass  2.240×3.920  2.240×3.920  8.781   8.781     1.00
nand2  ok   pass  pass      pass  3.360×3.920  2.800×3.920  13.171  10.976    1.20
nor2   ok   pass  pass      pass  3.360×3.920  3.360×3.920  13.171  13.171    1.00
aoi21  ok   pass  pass      pass  4.480×3.920  4.480×3.920  17.562  17.562    1.00
```

See `pdks/gf180/README.md` for the details.
