#include <iostream>
#include <cstdlib>
#include <sys/stat.h>
#include "compaction.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { std::cout << __FILE__ << ":" << __LINE__ << ": CHECK failed: " #cond << std::endl; ++failures; } } while (0)

// A stand-in for the highs executable: "...highs" in the name makes Compaction::solve use HiGHS's command line
// and read HiGHS's solution file. It records "<time limit> <seed>" of every call and behaves as $FAKE_MODE says.
static const char* FAKE = "tests/data/_fake_highs";
static const char* CALLS = "tests/data/_fake_highs.calls";

static const char* FAKE_SCRIPT = R"SH(#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in
    --time_limit) TL=$2; shift;;
    --random_seed) SEED=$2; shift;;
    --solution_file) SOL=$2; shift;;
  esac
  shift
done
echo "$TL $SEED" >> tests/data/_fake_highs.calls
none() { printf 'Model status\n%s\n\n# Primal solution values\nNone\n\n# Dual solution values\nNone\n\n# Basis\nHiGHS v1\nNone\n' "$1" > "$SOL"; }
feasible() { printf 'Model status\n%s\n\n# Primal solution values\nFeasible\nObjective %s\n# Columns 1\na %s\n\n# Dual solution values\nNone\n' "$1" "$2" "$2" > "$SOL"; }
case "$FAKE_MODE" in
  stall2)             if [ "$SEED" -lt 2 ]; then none "Time limit reached"; else feasible Optimal 5; fi;;
  stall)              none "Time limit reached";;
  capped_then_better) if [ "$TL" = 30 ]; then feasible "Time limit reached" 5; else feasible Optimal 7; fi;;
  capped_then_none)   if [ "$TL" = 30 ]; then feasible "Time limit reached" 5; else none "Time limit reached"; fi;;
  infeasible)         echo "  Status            Infeasible"; none Infeasible;;
  crash)              exit 1;;
esac
)SH";

struct Result { int ret; int a0; int a; vector<pair<int,int> > calls; };   // calls: (time limit, seed)

static Result run(const char* mode, int timeLimit) {
	setenv("FAKE_MODE", mode, 1);
	remove(CALLS);
	Compaction cpt(CP_LP, "tests/data/_ilp");
	cpt.insertConstraint("ZERO", "a", CP_MIN, 5);
	cpt.insertLPMinVar("a");
	Result r;
	r.a0 = cpt.getVariableVal("a");
	r.ret = cpt.solve(FAKE, timeLimit);
	r.a = cpt.getVariableVal("a");
	ifstream f(CALLS); int tl, seed;
	while (f >> tl >> seed) r.calls.push_back(make_pair(tl, seed));
	return r;
}

int main() {
	{ ofstream f(FAKE); f << FAKE_SCRIPT; }
	chmod(FAKE, 0755);

	// A seed that stalls is replaced by the next one, each attempt given twice the time of the one before.
	Result r = run("stall2", 600);
	CHECK(r.ret == 1);
	CHECK(r.a == 5);
	CHECK(r.calls.size() == 3);
	if (r.calls.size() == 3) {
		CHECK(r.calls[0] == make_pair(30, 0));
		CHECK(r.calls[1] == make_pair(60, 1));
		CHECK(r.calls[2] == make_pair(120, 2));
	}

	// No feasible point is a failure that leaves the variables alone, never a success. With a limit that
	// fits only one attempt there is no restart.
	r = run("stall", 1);
	CHECK(r.ret == 0);
	CHECK(r.a == r.a0);
	CHECK(r.calls.size() == 1);
	if (r.calls.size() == 1) CHECK(r.calls[0] == make_pair(1, 0));

	// A solver that dies without writing a solution file is an error, not a retry.
	bool threw = false;
	try { run("crash", 600); } catch (AstranError& e) { threw = true; }
	CHECK(threw);

	// A model the solver proves infeasible is not retried.
	r = run("infeasible", 600);
	CHECK(r.ret == 0);
	CHECK(r.calls.size() == 1);

	// A feasible point at the cap does not end the solve: the same seed gets the rest of the time.
	r = run("capped_then_better", 600);
	CHECK(r.ret == 1);
	CHECK(r.a == 7);
	CHECK(r.calls.size() == 2);
	if (r.calls.size() == 2) {
		CHECK(r.calls[0] == make_pair(30, 0));
		CHECK(r.calls[1].second == 0);
		CHECK(r.calls[1].first >= 590 && r.calls[1].first <= 600);
	}

	// If that second run finds nothing, the point found at the cap is kept.
	r = run("capped_then_none", 600);
	CHECK(r.ret == 1);
	CHECK(r.a == 5);
	CHECK(r.calls.size() == 2);

	// Every attempt stalling ends the solve once the last one, which gets all the time left, has stalled too.
	r = run("stall", 600);
	CHECK(r.ret == 0);
	CHECK(r.a == r.a0);
	CHECK(r.calls.size() == 5);

	remove(FAKE); remove(CALLS);
	remove("tests/data/_ilp.lp"); remove("tests/data/_ilp.sol"); remove("tests/data/_ilp.sol.probe");
	std::cout << (failures ? "FAILED" : "all passed") << ": " << failures << " failures" << std::endl;
	return failures ? 1 : 0;
}
