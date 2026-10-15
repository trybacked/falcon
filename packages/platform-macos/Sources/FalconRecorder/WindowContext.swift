import AppKit
import ApplicationServices

enum WindowContext {
    static func front() -> (app: String, window: String?) {
        guard let running = NSWorkspace.shared.frontmostApplication else {
            return ("", nil)
        }
        let app = running.localizedName ?? ""
        return (app, focusedWindowTitle(pid: running.processIdentifier))
    }

    private static func focusedWindowTitle(pid: pid_t) -> String? {
        let appEl = AXUIElementCreateApplication(pid)
        var winRef: CFTypeRef?
        guard AXUIElementCopyAttributeValue(appEl, kAXFocusedWindowAttribute as CFString, &winRef) == .success,
              let winRef
        else { return nil }
        let win = winRef as! AXUIElement
        var titleRef: CFTypeRef?
        guard AXUIElementCopyAttributeValue(win, kAXTitleAttribute as CFString, &titleRef) == .success,
              let title = titleRef as? String,
              !title.isEmpty
        else { return nil }
        return title
    }
}
