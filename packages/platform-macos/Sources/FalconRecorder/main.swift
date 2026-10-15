import AppKit
import ApplicationServices
import Foundation

struct Options {
    var output: String = "trace.raw.jsonl"
}

func parseArgs() -> Options {
    var opts = Options()
    var args = CommandLine.arguments.dropFirst()
    while let arg = args.first {
        args = args.dropFirst()
        switch arg {
        case "--output", "-o":
            if let path = args.first {
                opts.output = path
                args = args.dropFirst()
            }
        case "--help", "-h":
            fputs("Usage: falcon-recorder [--output PATH]\n", stderr)
            exit(0)
        default:
            if arg.hasPrefix("-") {
                fputs("Unknown option: \(arg)\n", stderr)
                exit(2)
            }
            opts.output = arg
        }
    }
    return opts
}

func requireAccessibility() {
    let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    if AXIsProcessTrustedWithOptions(opts) { return }
    if AXIsProcessTrusted() { return }
    fputs(
        "Accessibility permission required. Enable this binary in System Settings → Privacy & Security → Accessibility.\n",
        stderr
    )
    exit(1)
}

let options = parseArgs()
requireAccessibility()

let sessionId = UUID().uuidString
let writer: JSONLWriter
do {
    writer = try JSONLWriter(path: options.output)
} catch {
    fputs("Cannot open output: \(error.localizedDescription)\n", stderr)
    exit(1)
}

writer.append(.sessionStarted(sessionId: sessionId))

let recorder = EventTapRecorder(writer: writer, sessionId: sessionId)
guard recorder.start() else {
    fputs("Failed to create event tap. Check Accessibility and Input Monitoring permissions.\n", stderr)
    exit(1)
}

signal(SIGINT) { _ in
    CFRunLoopStop(CFRunLoopGetMain())
}
signal(SIGTERM) { _ in
    CFRunLoopStop(CFRunLoopGetMain())
}

fputs("Recording to \(options.output). Ctrl+C to stop.\n", stderr)
CFRunLoopRun()
recorder.stop()
writer.close()
