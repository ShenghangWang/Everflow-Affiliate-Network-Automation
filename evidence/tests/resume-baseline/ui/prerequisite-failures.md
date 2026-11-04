# Browser prerequisite evidence

First command: bundled Node `scripts/check_ui.mjs`; exit 1 before browser start.

```text
browserType.launch: Executable doesn't exist at /Users/shenghangwang/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-x64/chrome-headless-shell
```

The available local browser cache is revision 1228, not the bundled Playwright default 1234. The next attempt explicitly selects its existing headless Chromium executable. A successful check records the actual browser version and path; this does not claim the default browser was installed.

Second restricted launch selected the existing Chromium executable, then exited with SIGTRAP. Exact material diagnostic:

```text
FATAL:base/apple/mach_port_rendezvous_mac.cc:159] Check failed: kr == KERN_SUCCESS. bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer.54411: Permission denied (1100)
```

The same explicit-browser command was approved outside the restriction and completed all 12 UI checks. `browser-results.json` records actual browser identity, times and results. No automatic approval rejection was received.
