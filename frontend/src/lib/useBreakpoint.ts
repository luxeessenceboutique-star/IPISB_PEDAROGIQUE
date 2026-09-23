import { useState, useEffect } from "react";

export function useBreakpoint() {
  const [w, setW] = useState(() => (typeof window !== "undefined" ? window.innerWidth : 1280));
  useEffect(() => {
    const fn = () => setW(window.innerWidth);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return {
    isMobile: w < 640,   // phone
    isTablet: w < 1024,  // tablet + phone
    w,
  };
}
