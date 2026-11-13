/**
 \file compaction.cpp
 Compact layout. 
 \date 25-sep-2006 \author Cristiano Lazzari <clazz@inf.ufrgs.br> 
 */
#include <regex>
#include <chrono>
#include "compaction.h"
using namespace std;

/** Constructor. */
Compaction::Compaction( cp_algo a ,string name) {
	algo = a;
	lp_filename = name;
	variables.clear();
	constraints.clear();
}

/** Insert new variable. */
void Compaction::insertVal( string name ) {
	variables[name] = 0;
}

/** Insert new constraint. */
void Compaction::insertConstraintBTZ( string v1 ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.end();
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	cpc.type = CP_BIG_ZERO;
	
	constraints.push_back( cpc );
}

void Compaction::insertConstraint( string v1 ) {
    ctrts.push_back(v1);
}

/** Insert new constraint. */
void Compaction::insertConstraintEBTZ( string v1 ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.end();
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	cpc.type = CP_BIG_EQ_ZERO;
	
	constraints.push_back( cpc );
}

/** Insert new constraint. */
void Compaction::insertConstraintEZ( string v1 ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.end();
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	cpc.type = CP_EQ_ZERO;
	
	constraints.push_back( cpc );
}


/** Insert new constraint. */
void Compaction::insertConstraint( string v1, string v2, cp_cons_tp type, int val ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.find( v2 );
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		//    variables[v1] = 0;  
		cpc.v1 = variables.find( v1 );
	}
	
	if ( cpc.v2 == variables.end() ) {
		insertVal( v2 );
		//    variables[v2] = 0;  
		cpc.v2 = variables.find( v2 );
	}
	
	cpc.type = type;
	cpc.val = val;    
	
	constraints.push_back( cpc );
	
}

/** Insert new constraint. */
void Compaction::insertConstraint( string v1, string v2, cp_cons_tp type, string t ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.find( v2 );
	cpc.t  = variables.find( t );
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	if ( cpc.v2 == variables.end() ) {
		insertVal( v2 );
		cpc.v2 = variables.find( v2 );
	}
	if ( cpc.t == variables.end() ) {
		insertVal( t );
		cpc.t = variables.find( t );
	}
	
	if ( type == CP_EQ )
		cpc.type = CP_EQ_VAR;
	else if ( type == CP_MIN )
		cpc.type = CP_MIN_VAR;
	else if ( type == CP_MAX )
		cpc.type = CP_MAX_VAR;
	else
		cpc.type = type;
	
	constraints.push_back( cpc );  
}

/** Insert new constraint. */
void Compaction::insertConstraint( string v1, string v2, cp_cons_tp type, string t, int val ) {
	
	cp_constraint cpc;
	
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.find( v2 );
	cpc.t  = variables.find( t );
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	if ( cpc.v2 == variables.end() ) {
		insertVal( v2 );
		cpc.v2 = variables.find( v2 );
	}
	if ( cpc.t == variables.end() ) {
		insertVal( t );
		cpc.t = variables.find( t );
	}  
	
	if ( type == CP_EQ )
		cpc.type = CP_EQ_VAR_VAL;
	else if ( type == CP_MIN )
		cpc.type = CP_MIN_VAR_VAL;
	else if ( type == CP_MAX )
		cpc.type = CP_MAX_VAR_VAL;
	else
		cpc.type = type;
	
	cpc.val = val;
	
	constraints.push_back( cpc );  
}

/** Insert Upper Bound. */
void Compaction::insertUpperBound( string v1, int val ) {
	
	cp_constraint cpc;
    
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.end();
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	cpc.type = CP_UPPER_BOUND;
	cpc.val = val;
	
	constraints.push_back( cpc );
}

/** Insert Upper Bound. */
void Compaction::insertLowerBound( string v1, int val ) {
	
	cp_constraint cpc;
    
	cpc.v1 = variables.find( v1 );
	cpc.v2 = variables.end();
	cpc.t  = variables.end();
	
	if ( cpc.v1 == variables.end() ) {
		insertVal( v1 );
		cpc.v1 = variables.find( v1 );
	}
	
	cpc.type = CP_LOWER_BOUND;
	cpc.val = val;
	
	constraints.push_back( cpc );
}

/** Force these variavles to be integer. */
void Compaction::forceIntegerVar( string v ) {
	if (std::find(int_vars.begin(), int_vars.end(), v) == int_vars.end()) {
		//if (int_vars.size()<715) {
			int_vars.push_back( v );
		//}
	}
}

/** Force these variavles to be binary. */
void Compaction::forceBinaryVar( string v ) {
	bin_vars.push_back( v );
}

/** Force these variavles to be semi-continuous (0 or interval). */
void Compaction::forceSecVar( string v ) {
	sec_vars.push_back( v );
}

/** Force these variavles to be special ordered set. */
void Compaction::forceSOS( string v ) {
	sos_vars.push_back( v );
}


/** Insert LP variable. These variables are include in the minimization objective function. */
void Compaction::insertLPMinVar( string v ) {
	lp_min_var.push_back( v );
	lp_min_val.push_back( 1 );
}

/** Insert LP variable. These variables are include in the minimization objective function. */
void Compaction::insertLPMinVar( string v, int i ) {
	lp_min_var.push_back( v );
	lp_min_val.push_back( i );
}

/*
 int Compaction::solve(string lpSolverFile) {
 cout << "-> Calling LP Solver (" 
 << variables.size() << " variables, " 
 << constraints.size() << " constraints)" << endl;
 
 string fn = lp_filename + ".lp";
 ofstream f(fn.c_str());
 
 
 if ( !f ) {
 cerr << "ERROR:Cannot create file " << fn << ". Please verify your temporary directory." << endl;
 exit(-1);
 }
 
 f << "min: "; 
 for ( unsigned int i = 0; i < lp_min_var.size(); i++ ) {    
 if ( i != 0 )
 f << " + ";
 if ( lp_min_val[i] != 1 )
 f << lp_min_val[i] << " ";
 
 f << lp_min_var[i];
 }
 f << ";" << endl;
 
 // Constant zero
 variables[ "ZERO" ] = 0;
 f << "Czero: ZERO = 0;" << endl;
 
 for ( unsigned int i = 0; i < constraints.size(); i++ ) {
 
 string v1 = constraints[i].v1->first;
 
 string v2  = "0";
 if ( constraints[i].v2 != variables.end() )
 v2 = constraints[i].v2->first;
 
 string t  = "0";
 if ( constraints[i].t != variables.end() )
 t = constraints[i].t->first;
 
 cp_cons_tp type = constraints[i].type;
 
 int val = constraints[i].val;
 
 if ( type == CP_MIN )
 f << "C" << i << ": " << v2 << " - " << v1 << " >= " << val << ";" << endl;
 if ( type == CP_MAX )
 f << "C" << i << ": " << v2 << " - " << v1 << " <= " << val << ";" << endl;
 else if ( type == CP_EQ )
 f << "C" << i << ": " << v2 << " - " << v1 << " = " << val << ";" << endl;
 else if ( type == CP_MIN_VAR_VAL )
 f << "C" << i << ": " << v2 << " - " << v1 << " >= " << val << " " << t << ";" << endl;
 else if ( type == CP_MAX_VAR_VAL )
 f << "C" << i << ": " << v2 << " - " << v1 << " <= " << val << " " << t << ";" << endl;
 else if ( type == CP_EQ_VAR_VAL )
 f << "C" << i << ": " << v2 << " - " << v1 << " = " << val << " " << t << ";" << endl;
 else if ( type == CP_MIN_VAR )
 f << "C" << i << ": " << v2 << " - " << v1 << " >= " << t << ";" << endl;
 else if ( type == CP_MAX_VAR )
 f << "C" << i << ": " << v2 << " - " << v1 << " <= " << t << ";" << endl;
 else if ( type == CP_EQ_VAR )
 f << "C" << i << ": " << v2 << " - " << v1 << " = " << t << ";" << endl;
 else if ( type == CP_BIG_ZERO )
 f << "C" << i << ": " << v1 << " > 0;" << endl;
 else if ( type == CP_BIG_EQ_ZERO )
 f << "C" << i << ": " << v1 << " >= 0;" << endl;
 else if ( type == CP_EQ_ZERO )
 f << "C" << i << ": " << v1 << " = 0;" << endl;
 else if ( type == CP_UPPER_BOUND )
 f << "C" << i << ": " << v1 << " <= " << val << ";" << endl;
 else if ( type == CP_LOWER_BOUND )
 f << "C" << i << ": " << v1 << " >= " << val << ";" << endl;
 
 }
 
 if ( int_vars.size() > 0 ) {  
 f << "int "; 
 for ( unsigned int i = 0; i < int_vars.size(); i++ ) {
 if ( i != 0 )
 f << ", ";
 f << int_vars[i];
 }
 f << ";" << endl;
 }
 
 if ( bin_vars.size() > 0 ) {  
 f << "bin "; 
 for ( unsigned int i = 0; i < bin_vars.size(); i++ ) {
 if ( i != 0 )
 f << ", ";
 f << bin_vars[i];
 }
 f << ";" << endl;
 }
 
 if ( sec_vars.size() > 0 ) {  
 f << "sec "; 
 for ( unsigned int i = 0; i < sec_vars.size(); i++ ) {
 if ( i != 0 )
 f << ", ";
 f << sec_vars[i];
 }
 f << ";" << endl;
 }
 
 if ( sos_vars.size() > 0 ) {  
 f << "sos" << endl; 
 for ( unsigned int i = 0; i < sos_vars.size(); i++ )
 f << "SOS" << i << ": " << sos_vars[i] << " <= 1;" << endl;
 }
 
 
 f.close();
 string cmd = "\"" + lpSolverFile + "\" " + 	lp_filename + ".lp 2> temp.log";
 cout << "-> Running command: " << cmd << endl;
 
 FILE *x = _popen(cmd.c_str(), "r");
 
 if(x==NULL){
 cout << "-> ERROR: Problem to execute lp_solve!" << endl;
 return 0;
 }
 
 char str[150];
 while (fgets(str, 150, x)) {
 
 istringstream s(str);
 
 string n;
 int v;
 
 s >> n;
 if(n=="This"){
 cout << "-> Error executing LP Solver: " << str << endl;
 return 0;
 }
 s >> v;
 
 
 map<string,int>::iterator i = variables.find( n );
 if ( i != variables.end() ) {
 i->second = v;
 }
 }
 
 _pclose(x);
 return 1;
 }
 */

/** Solve Compaction constraints with linear programming. */
/** Time cap in seconds of the first HiGHS attempt; every restart doubles it. */
static const int SOLVE_FIRST_ATTEMPT_CAP = 30;

/** Read the values a solver wrote into \a variables. Returns how many were read: 0 means the solver left no
 solution (HiGHS writes "None" when it stopped without a feasible point, and the variables must then stay untouched).
 \a hitTimeLimit tells whether HiGHS stopped because of its time limit. */
static int readSolution(const string &fileName, map<string,int> &variables, bool highs, bool &hitTimeLimit) {
    hitTimeLimit = false;
    ifstream f(fileName.c_str());
    if(!f)
        throw AstranError("Problem opening: " + fileName);
    
    string line;
    int nRead = 0;
    while (getline(f, line)) {
        if(line=="Model status"){
            getline(f, line);
            hitTimeLimit = (line=="Time limit reached");
            continue;
        }
        if(!line.empty() && line[0]=='#'){
            //HiGHS also writes "# Dual solution values" and "# Basis" sections (pure LPs), with the same
            //column names: stop at the end of the primal values so they don't overwrite them.
            if(line.find("Dual solution")!=string::npos || line.find("Basis")!=string::npos)
                break;
            if(highs && line.find("Primal solution")!=string::npos){
                getline(f, line);
                if(line!="Feasible")
                    return 0;
            }
            continue;
        }
        
        istringstream s(line);
        string n;
        double tmp;
        if(!(s >> n >> tmp))
            continue;
        
        map<string,int>::iterator i = variables.find( n );
        if ( i != variables.end() ) {
            i->second = round(tmp);
            nRead++;
        }
    }
    return nRead;
}

int Compaction::solve(string lpSolverFile, int timeLimit) {
	cout << "-> Calling LP Solver (" 
	<< variables.size() << " variables, " 
	<< constraints.size() << " constraints)" << endl;
	
	string fn = lp_filename + ".lp";
    {
        ofstream f(fn.c_str());
        
        if ( !f )
            throw AstranError("Cannot create file " + fn);
        
        f << "Minimize" << endl; 
        for ( unsigned int i = 0; i < lp_min_var.size(); i++ ) {    
            if ( i != 0 ){
                if(lp_min_val[i]>=0)
                    f << " + ";
                else
                    f << " - ";
            } else if ( lp_min_val[i] < 0 )
                f << "- ";
            if ( lp_min_val[i] != 1 )
                f << abs(lp_min_val[i]) << " ";
            
            f << lp_min_var[i];
        }
        f << endl;
        
        f << "Subject To" << endl; 
        
        // Constant zero
        variables[ "ZERO" ] = 0;
        f << "Czero: ZERO = 0" << endl;
        unsigned int i;
		
        for (i = 0; i < constraints.size(); i++ ) {
            
            string v1 = constraints[i].v1->first;
            
            string v2  = "0";
            if ( constraints[i].v2 != variables.end() )
                v2 = constraints[i].v2->first;
            
            string t  = "0";
            if ( constraints[i].t != variables.end() )
                t = constraints[i].t->first;
            
            cp_cons_tp type = constraints[i].type;
            
            int val = constraints[i].val;
            
            if ( type == CP_MIN )
                f << "C" << i << ": " << v2 << " - " << v1 << " >= " << val << endl;
            if ( type == CP_MAX )
                f << "C" << i << ": " << v2 << " - " << v1 << " <= " << val << endl;
            else if ( type == CP_EQ)
                f << "C" << i << ": " << v2 << " - " << v1 << " = " << val << endl;
            else if ( type == CP_MIN_VAR_VAL )
                f << "C" << i << ": " << v2 << " - " << val << " " << t << " - " << v1 << " >= 0" << endl;
            else if ( type == CP_MAX_VAR_VAL )
                f << "C" << i << ": " << v2 << " - " << val << " " << t << " - " << v1 << " <= 0" << endl;
            else if ( type == CP_EQ_VAR_VAL )
                f << "C" << i << ": " << v2 << " - " << val << " " << t << " - " << v1 << " = 0" << endl;
            else if ( type == CP_MIN_VAR )
                f << "C" << i << ": " << v2 << " - " << v1 << " - " << t << " >= 0" << endl;
            else if ( type == CP_MAX_VAR )
                f << "C" << i << ": " << v2 << " - " << v1 << " - " << t << " <= 0" << endl;
            else if ( type == CP_EQ_VAR )
                f << "C" << i << ": " << v2 << " - " << v1 << " - " << t << " = 0" << endl;
            else if ( type == CP_BIG_ZERO )
                f << "C" << i << ": " << v1 << " > 0" << endl;
            else if ( type == CP_BIG_EQ_ZERO )
                f << "C" << i << ": " << v1 << " >= 0" << endl;
            else if ( type == CP_EQ_ZERO )
                f << "C" << i << ": " << v1 << " = 0" << endl;
            else if ( type == CP_UPPER_BOUND )
                f << "C" << i << ": " << v1 << " <= " << val << endl;
            else if ( type == CP_LOWER_BOUND )
                f << "C" << i << ": " << v1 << " >= " << val << endl;
            
        }
		
        for ( unsigned int j = 0; j < ctrts.size(); j++ ) {
            f << "C" << i+j << ": " << ctrts[j] << endl;
        }
        
        if ( int_vars.size() > 0 ) {  
            f << "Generals" << endl; 
            //for (map<string,int>::iterator it = variables.begin();it != variables.end(); ++it){
            //	if ( it != variables.begin() )
			//   		f << " ";
			//	f << it->first;
            //}
			for ( unsigned int i = 0; i < int_vars.size(); i++ ) {
				if (std::find(bin_vars.begin(), bin_vars.end(), int_vars[i]) == bin_vars.end()) {
 					if ( i != 0 )
 						f << " ";
 					f << int_vars[i];
				}
			}
            f << endl;
        }
        
        if ( bin_vars.size() > 0 ) {  
            f << "Binary" << endl; 
            for ( unsigned int i = 0; i < bin_vars.size(); i++ ) {
                if ( i != 0 )
                    f << " ";
                f << bin_vars[i];
            }
            f << endl;
        }
        
        if ( sec_vars.size() > 0 ) {  
            f << "Semi" << endl;
            for ( unsigned int i = 0; i < sec_vars.size(); i++ ) {
                if ( i != 0 )
                    f << " ";
                f << sec_vars[i];
            }
            f << endl;
        }
        
        if ( sos_vars.size() > 0 ) {  
            f << "sos" << endl; 
            for ( unsigned int i = 0; i < sos_vars.size(); i++ )
                f << "SOS" << i << ": " << sos_vars[i] << " <= 1" << endl;
        }
        
        f << "End" << endl;
        f.flush();
        f.close();
    }

    string solFileName = lp_filename + ".sol";
    
    regex str_expr_scip ("(.*)scip");
    regex str_expr_highs ("(.*)highs");
    bool isHighs = regex_match(lpSolverFile,str_expr_highs);
    bool isScip = !isHighs && regex_match(lpSolverFile,str_expr_scip);
    
    struct Attempt { bool infeasible; int nRead; bool hitTimeLimit; };
    
    // One run of the solver. Leaves the values it found, if any, in the variables.
    auto attempt = [&](int limit, int seed) -> Attempt {
        remove(solFileName.c_str()); //never read a solution left by an earlier run
        
        string cmd;
        if (isHighs)
            cmd = "\"" + lpSolverFile + "\" --time_limit " + to_string(limit) + " --random_seed " + to_string(seed) + "  --solution_file " + solFileName + " " + lp_filename + ".lp";
        else if (isScip)
            cmd = "\"" + lpSolverFile +  "\"  -l " + solFileName + " -f " + lp_filename + ".lp";
        else
            cmd = "\"" + lpSolverFile + "\" TimeLimit=" + to_string(limit) + " ResultFile=" + solFileName + " " + lp_filename + ".lp";
        
        cout << "-> Running command: " << cmd << endl;
        
        FILE *x = _popen(cmd.c_str(), "r");
        
        if(x==NULL)
            throw AstranError("Problem executing: " + cmd);
        
        cout << "-> To interrupt earlier and get the current best solution, type in a terminal: kill -2 [gurobi process]" << endl;
        cout << "-> * and H means new feasible solution found:";
        cerr << " ";
        
        char line[150];
        
        bool infeasible=false;
        while (fgets(line, 150, x)) {
            istringstream s(line);
            string n;		
            s >> n;
            if(n!="Warning:")
                printf("%s",line);
            
            if(n=="H" || n=="*")
                cerr << n;
            
            //"infeasible" (not "infeasibility"/"infeasibilities", which also appear in feasible solves' logs)
            string lowerLine(line);
            transform(lowerLine.begin(), lowerLine.end(), lowerLine.begin(), ::tolower);
            if(lowerLine.find("infeasible")!=string::npos) infeasible=true;
            
            if(n=="ERROR" || n=="Time" || n=="Unable" || n=="Wrote" || n=="Optimal" || n=="Model")
                cout << endl << line;
        }
        
        _pclose(x);
        
        Attempt a = {infeasible, 0, false};
        if(!infeasible)
            a.nRead = readSolution(solFileName, variables, isHighs, a.hitTimeLimit);
        return a;
    };
    
    auto start = chrono::steady_clock::now();
    auto remainingTime = [&]() -> int {
        return timeLimit - (int) chrono::duration_cast<chrono::seconds>(chrono::steady_clock::now() - start).count();
    };
    
    // HiGHS can stall without ever finding a feasible point, and whether it does depends on its random seed:
    // the same model that stalls with one seed is solved in a few seconds with another. So the first attempt
    // is capped, and an attempt that ends at its cap with no solution is repeated with the next seed and a
    // cap twice as long. The last attempt, the one that no longer fits twice, takes whatever time is left.
    int cap = SOLVE_FIRST_ATTEMPT_CAP;
    int seed = 0;
    
    while(true){
        int remaining = remainingTime();
        if(remaining < 1){
            cout << endl << "-> No feasible solution was found within the time limit of " << timeLimit << " s" << endl;
            return 0;
        }
        bool capped = isHighs && remaining > 2 * cap;
        
        Attempt a = attempt(capped ? cap : remaining, seed);
        
        if(a.infeasible){
            cout << "-> The solver reported that the model is infeasible" << endl;
            return 0;
        }
        
        if(a.nRead > 0){
            if(!(capped && a.hitTimeLimit))
                return 1;
            
            // A feasible point at the cap, but the solver was still improving it. A stopped HiGHS cannot be
            // resumed, so run the same seed again for the rest of the time and keep this solution in case
            // that run ends without one.
            cout << endl << "-> Feasible solution found with seed " << seed << ", running it again for the remaining time" << endl;
            string probeFileName = solFileName + ".probe";
            rename(solFileName.c_str(), probeFileName.c_str());
            
            remaining = remainingTime();
            if(remaining >= 1 && attempt(remaining, seed).nRead > 0)
                return 1;
            
            bool ignored;
            readSolution(probeFileName, variables, isHighs, ignored);
            return 1;
        }
        
        // No solution: a HiGHS that stalled at its cap is retried with another seed, anything else is a failure
        // (an attempt that was already given all the remaining time leaves nothing to retry with).
        if(!(capped && a.hitTimeLimit)){
            cout << endl << (isHighs && a.hitTimeLimit ? "-> No feasible solution was found within the time limit"
                                                       : "-> The solver stopped without finding a solution") << endl;
            return 0;
        }
        cout << endl << "-> No feasible solution after " << (capped ? cap : remaining) << " s with seed " << seed
             << ", trying seed " << seed + 1 << endl;
        seed++;
        cap *= 2;
    }
}


/** Get variables values. */
int Compaction::getVariableVal( string name ) {
	map<string,int>::iterator i = variables.find( name );
	if ( i != variables.end() ) 
		return i->second;
	return -1;  
}