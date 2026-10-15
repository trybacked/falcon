import Foundation

struct TraceEvent: Encodable {
    let kind: String
    let ts: Double
    var sessionId: String?
    var x: Int?
    var y: Int?
    var button: String?
    var text: String?
    var app: String?
    var window: String?

    static func now() -> Double {
        Date().timeIntervalSince1970
    }

    static func sessionStarted(sessionId: String) -> TraceEvent {
        TraceEvent(kind: "session.started", ts: now(), sessionId: sessionId)
    }

    static func sessionEnded(sessionId: String) -> TraceEvent {
        TraceEvent(kind: "session.ended", ts: now(), sessionId: sessionId)
    }

    static func mouseClick(x: Int, y: Int, button: String, sessionId: String) -> TraceEvent {
        TraceEvent(
            kind: "mouse.click",
            ts: now(),
            sessionId: sessionId,
            x: x,
            y: y,
            button: button
        )
    }

    static func textInput(_ text: String, sessionId: String) -> TraceEvent {
        TraceEvent(kind: "keyboard.text_input", ts: now(), sessionId: sessionId, text: text)
    }

    static func submit(_ text: String, sessionId: String) -> TraceEvent {
        TraceEvent(kind: "keyboard.submit", ts: now(), sessionId: sessionId, text: text)
    }

    static func windowChanged(app: String, window: String?, sessionId: String) -> TraceEvent {
        TraceEvent(
            kind: "window.changed",
            ts: now(),
            sessionId: sessionId,
            app: app,
            window: window
        )
    }
}
