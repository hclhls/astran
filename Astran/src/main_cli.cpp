// Command-line entry point without wxWidgets.
// Usage: astran-cli <script.run>
// Runs each non-comment line of the script through DesignMng::readCommand.
// Exit status: 0 at end of file or EXIT, 1 at the first failing line, 2 if the
// script cannot be opened.
#include <clocale>
#include <fstream>
#include <iostream>
#include <string>
#include "designmng.h"

int main(int argc, char** argv) {
	if (argc != 2) {
		std::cerr << "usage: astran-cli <script.run>" << std::endl;
		return 2;
	}
	setlocale(LC_ALL, "C");
	const std::string script = argv[1];
	std::ifstream file(script.c_str());
	if (!file) {
		std::cout << "ERROR: File '" << script << "' doesn't exist" << std::endl;
		return 2;
	}
	DesignMng designmng;
	std::string line;
	int lineno = 0;
	while (std::getline(file, line)) {
		++lineno;
		if (!line.empty() && line[line.size() - 1] == '\r')
			line.erase(line.size() - 1);
		if (line.empty() || line[0] == '*')
			continue;
		std::cout << "astran> " << line << std::endl;
		if (!designmng.readCommand(line)) {
			std::cout << "ERROR: " << script << ":" << lineno << std::endl;
			return 1;
		}
	}
	return 0;
}
