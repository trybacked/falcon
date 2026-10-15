import ApplicationServices
import AppKit
import Carbon

final class EventTapRecorder {
    private let writer: JSONLWriter
    private let sessionId: String
    private var tap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private var textBuffer = ""
    private var lastWindowKey = ""

    init(writer: JSONLWriter, sessionId: String) {
        self.writer = writer
        self.sessionId = sessionId
    }

    func start() -> Bool {
        let mask =
            (1 << CGEventType.leftMouseDown.rawValue)
            | (1 << CGEventType.rightMouseDown.rawValue)
            | (1 << CGEventType.otherMouseDown.rawValue)
            | (1 << CGEventType.keyDown.rawValue)

        let refcon = Unmanaged.passUnretained(self).toOpaque()
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: CGEventMask(mask),
            callback: Self.callback,
            userInfo: refcon
        ) else {
            return false
        }
        self.tap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)

        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(appActivated),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )
        emitWindowIfChanged()
        return true
    }

    func stop() {
        if let tap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
        if let runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        }
        NSWorkspace.shared.notificationCenter.removeObserver(self)
        flushTextInput()
        writer.append(.sessionEnded(sessionId: sessionId))
    }

    @objc private func appActivated() {
        emitWindowIfChanged()
    }

    private func emitWindowIfChanged() {
        let ctx = WindowContext.front()
        let key = "\(ctx.app)|\(ctx.window ?? "")"
        guard key != lastWindowKey else { return }
        lastWindowKey = key
        guard !ctx.app.isEmpty else { return }
        writer.append(.windowChanged(app: ctx.app, window: ctx.window, sessionId: sessionId))
    }

    fileprivate func handle(type: CGEventType, event: CGEvent) {
        switch type {
        case .leftMouseDown, .rightMouseDown, .otherMouseDown:
            let loc = event.location
            let button: String
            switch type {
            case .rightMouseDown: button = "right"
            case .otherMouseDown: button = "other"
            default: button = "left"
            }
            writer.append(
                .mouseClick(
                    x: Int(loc.x),
                    y: Int(loc.y),
                    button: button,
                    sessionId: sessionId
                )
            )
        case .keyDown:
            handleKeyDown(event)
        default:
            break
        }
    }

    private func handleKeyDown(_ event: CGEvent) {
        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
        if keyCode == kVK_Return || keyCode == kVK_ANSI_KeypadEnter {
            let line = textBuffer
            textBuffer = ""
            writer.append(.submit(line, sessionId: sessionId))
            return
        }
        if keyCode == kVK_Delete || keyCode == kVK_ForwardDelete {
            if !textBuffer.isEmpty {
                textBuffer.removeLast()
                writer.append(.textInput(textBuffer, sessionId: sessionId))
            }
            return
        }
        var length = 0
        var chars = [UniChar](repeating: 0, count: 4)
        event.keyboardGetUnicodeString(maxStringLength: 4, actualStringLength: &length, unicodeString: &chars)
        guard length > 0 else { return }
        let scalar = String(utf16CodeUnits: chars, count: length)
        textBuffer.append(scalar)
        writer.append(.textInput(textBuffer, sessionId: sessionId))
    }

    private func flushTextInput() {
        guard !textBuffer.isEmpty else { return }
        writer.append(.textInput(textBuffer, sessionId: sessionId))
    }

    private static let callback: CGEventTapCallBack = { _, type, event, refcon in
        guard let refcon else { return Unmanaged.passUnretained(event) }
        let recorder = Unmanaged<EventTapRecorder>.fromOpaque(refcon).takeUnretainedValue()
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if let tap = recorder.tap {
                CGEvent.tapEnable(tap: tap, enable: true)
            }
            return Unmanaged.passUnretained(event)
        }
        recorder.handle(type: type, event: event)
        return Unmanaged.passUnretained(event)
    }
}
