import Foundation

final class JSONLWriter {
    private let url: URL
    private let handle: FileHandle
    private let lock = NSLock()

    init(path: String) throws {
        url = URL(fileURLWithPath: path)
        let dir = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: path) {
            FileManager.default.createFile(atPath: path, contents: nil)
        }
        handle = try FileHandle(forWritingTo: url)
        try handle.seekToEnd()
    }

    func append(_ event: TraceEvent) {
        lock.lock()
        defer { lock.unlock() }
        guard let data = try? JSONEncoder.falcon.encode(event),
              var line = String(data: data, encoding: .utf8)
        else { return }
        line.append("\n")
        if let bytes = line.data(using: .utf8) {
            handle.write(bytes)
        }
    }

    func close() {
        try? handle.close()
    }
}

extension JSONEncoder {
    static let falcon: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys]
        return e
    }()
}
