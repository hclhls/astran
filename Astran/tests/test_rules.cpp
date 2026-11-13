#include <iostream>
#include "rules.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { std::cout << __FILE__ << ":" << __LINE__ << ": CHECK failed: " #cond << std::endl; ++failures; } } while (0)

int main() {
	Rules r; r.readRules("tests/data/dt.rul");
	CHECK(r.getGDSIILayer(MET1).layer == 67 && r.getGDSIILayer(MET1).datatype == 20);
	CHECK(r.getGDSIILayer(POLY).layer == 9  && r.getGDSIILayer(POLY).datatype == 0);
	CHECK(r.getGDSIILayer(CONT).set == false);
	CHECK(r.getLabelGDSIILayer().layer == 67 && r.getLabelGDSIILayer().datatype == 5);
	CHECK(r.getGDSIIVal(MET1) == "67/20");

	Rules legacy; legacy.readRules("build/Work/tech_freePDK45.rul");
	CHECK(legacy.getGDSIILayer(MET1).layer == 11 && legacy.getGDSIILayer(MET1).datatype == 0);
	CHECK(legacy.getLabelGDSIILayer().layer == 11 && legacy.getLabelGDSIILayer().datatype == 0);
	Rules a, b; a.readRules("build/Work/tech_035.rul"); b.readRules("build/Work/tech_0065.rul");   // must not throw

	// Review Focus 1: each of these files has one bad GDSII value on line 3
	for (const char* f : {"bad_trailing.rul", "bad_alpha.rul", "bad_three.rul", "bad_range.rul"}) {
		bool threw = false; string msg;
		try { Rules x; x.readRules(string("tests/data/") + f); }
		catch (AstranError& e) { threw = true; msg = e.what(); }
		CHECK(threw);
		CHECK(msg.find(":3") != string::npos);
		CHECK(msg.find(f) != string::npos);
	}

	// the table written for Cadence carries layer and datatype in separate columns
	r.saveGDSIILayerTable("tests/data/_out.lyt");
	{
		ifstream f("tests/data/_out.lyt"); string l, all;
		while (getline(f, l)) all += l + "\n";
		CHECK(all.find("67\t\t20") != string::npos);
	}
	remove("tests/data/_out.lyt");

	// generic slot for the diffusion enclosure of a tap contact; 0 in rule files that do not set it
	CHECK(a.getRule(E3DFCT) == 0);
	Rules t; t.readRules("tests/data/dt.rul");
	CHECK(t.getRule(E3DFCT) == 24);    // 0.12 um at MINSTEP 0.005

	std::cout << (failures ? "FAILED" : "all passed") << ": " << failures << " failures" << std::endl;
	return failures ? 1 : 0;
}
