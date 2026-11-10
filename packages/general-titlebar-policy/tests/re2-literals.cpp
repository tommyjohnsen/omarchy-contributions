#include <re2/re2.h>
#include <iostream>
#include <string>
int main() {
  std::string line;
  unsigned count = 0;
  while (std::getline(std::cin, line)) {
    const auto tab = line.find('\t');
    if (tab == std::string::npos) return 1;
    const auto id = line.substr(0, tab);
    const auto pattern = line.substr(tab + 1);
    const RE2 re(pattern);
    if (!re.ok() || !RE2::FullMatch(id, re) || RE2::FullMatch(id + "extra", re)) {
      std::cerr << "Invalid literal match: " << pattern << '\n';
      return 1;
    }
    ++count;
  }
  if (count != 4) return 1;
  std::cout << "PASS: four escaped literals compile and match exactly in installed RE2\n";
}
