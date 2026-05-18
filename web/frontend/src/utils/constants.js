export const MODULES = [
  { id: 'subdomain', name: 'Subdomain Enumeration', num: 1, phase: 1, tool: 'Subfinder, Amass, Assetfinder' },
  { id: 'dns', name: 'DNS Resolution', num: 2, phase: 1, tool: 'dnsx' },
  { id: 'alive', name: 'Alive Hosts Check', num: 3, phase: 1, tool: 'httpx' },
  { id: 'dnsbrute', name: 'DNS Bruteforce', num: 17, phase: 1, tool: 'massdns' },
  { id: 'ports', name: 'Fast Port Scan', num: 4, phase: 2, tool: 'Naabu / Nmap' },
  { id: 'fullports', name: 'Full Port Scan', num: 5, phase: 2, tool: 'Nmap' },
  { id: 'waf', name: 'WAF Detection', num: 7, phase: 2, tool: 'wafw00f' },
  { id: 'screenshots', name: 'Screenshot Capture', num: 16, phase: 2, tool: 'gowitness + EyeWitness' },
  { id: 'tech', name: 'Tech Fingerprint', num: 19, phase: 2, tool: 'WhatWeb' },
  { id: 'asn', name: 'ASN Discovery', num: 24, phase: 2, tool: 'asnmap' },
  { id: 'urls', name: 'URL Collection', num: 6, phase: 3, tool: 'Katana, gau, waybackurls' },
  { id: 'params', name: 'Parameter Discovery', num: 10, phase: 3, tool: 'ParamSpider, Arjun' },
  { id: 'js', name: 'JS Endpoint Extraction', num: 11, phase: 3, tool: 'LinkFinder' },
  { id: 'fuzz', name: 'Directory Fuzzing', num: 12, phase: 3, tool: 'ffuf' },
  { id: 'api', name: 'API Fuzzing', num: 13, phase: 3, tool: 'Kiterunner' },
  { id: 'takeover', name: 'Subdomain Takeover', num: 14, phase: 3, tool: 'subzy' },
  { id: 'hakrawler', name: 'Advanced URL Enum', num: 15, phase: 3, tool: 'hakrawler' },
  { id: 'vuln', name: 'Vulnerability Scan', num: 8, phase: 4, tool: 'Nuclei' },
  { id: 'gf', name: 'GF Pattern Filters', num: 18, phase: 4, tool: 'gf' },
  { id: 'sqli', name: 'SQLi Scan', num: 20, phase: 4, tool: 'sqlmap' },
  { id: 'xss', name: 'XSS Scan', num: 21, phase: 4, tool: 'Dalfox' },
  { id: 'cors', name: 'CORS Scanner', num: 22, phase: 4, tool: 'Python' },
  { id: 'redirect', name: 'Open Redirect Scan', num: 29, phase: 4, tool: 'Python' },
  { id: 'smuggling', name: 'HTTP Smuggling', num: 23, phase: 5, tool: 'smuggler' },
  { id: 'cloud', name: 'Cloud Asset Discovery', num: 25, phase: 5, tool: 'Python' },
  { id: 'github', name: 'GitHub Dorking', num: 26, phase: 5, tool: 'GitHub API' },
  { id: 'osint', name: 'OSINT Harvesting', num: 27, phase: 5, tool: 'theHarvester' },
  { id: 'shodan', name: 'Shodan Recon', num: 28, phase: 5, tool: 'Shodan API' },
];

export const PHASES = {
  1: { name: 'Discovery', color: '#00D4AA' },
  2: { name: 'Infrastructure', color: '#3B82F6' },
  3: { name: 'Content Discovery', color: '#8B5CF6' },
  4: { name: 'Vulnerability Analysis', color: '#F59E0B' },
  5: { name: 'OSINT & Intel', color: '#EF4444' },
};

export const SCAN_MODES = [
  { id: 'quick', name: 'Quick Recon', desc: 'Core pipeline (modules 1-8)', icon: 'Zap' },
  { id: 'deep', name: 'Deep Recon', desc: '14 advanced modules', icon: 'Layers' },
  { id: 'full_spectrum', name: 'Full Spectrum', desc: 'All 29 modules, 5 phases', icon: 'Globe' },
  { id: 'custom', name: 'Custom', desc: 'Pick individual modules', icon: 'Settings' },
];

export const VIEWS = {
  SCAN: 'scan',
  LIVE: 'live',
  RESULTS: 'results',
  REPORTS: 'reports',
  TOOLS: 'tools',
  HISTORY: 'history',
};
