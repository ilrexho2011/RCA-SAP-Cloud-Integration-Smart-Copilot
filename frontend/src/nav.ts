export interface NavItem {
  id: string;
  no: string;
  label: string;
  path: string;
}

/* Product navigation — the CPI Copilot module set, styled in the QDKEP theme. */
export const NAV: NavItem[] = [
  { id: "dashboard", no: "01", label: "Dashboard", path: "/" },
  { id: "generate",  no: "02", label: "Generate",  path: "/generate" },
  { id: "iflows",    no: "03", label: "iFlows",    path: "/iflows" },
  { id: "groovy",    no: "04", label: "Groovy",    path: "/groovy" },
  { id: "monitor",   no: "05", label: "Monitor",   path: "/monitor" },
  { id: "knowledge", no: "06", label: "Knowledge", path: "/knowledge" },
  { id: "settings",  no: "07", label: "Settings",  path: "/settings" },
];
