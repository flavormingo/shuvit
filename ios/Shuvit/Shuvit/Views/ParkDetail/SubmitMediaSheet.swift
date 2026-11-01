import AVFoundation
import CoreTransferable
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct SubmitMediaSheet: View {
    let parkId: UUID
    @Environment(\.dismiss) private var dismiss

    @State private var selectedItem: PhotosPickerItem?
    @State private var selection: SelectedMedia?
    @State private var isPreparing = false
    @State private var description = ""
    @State private var tags = ""
    @State private var isUploading = false
    @State private var errorMessage: String?
    @State private var uploadSuccess = false

    private static let maxVideoBytes = 50 * 1024 * 1024

    var body: some View {
        NavigationStack {
            Form {
                Section("Select Media") {
                    PhotosPicker(selection: $selectedItem, matching: .any(of: [.images, .videos])) {
                        if isPreparing {
                            Label("Preparing…", systemImage: "hourglass")
                        } else if let selection {
                            Label(selection.isVideo ? "Video selected" : "Photo selected", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        } else {
                            Label("Choose photo or video", systemImage: "photo.on.rectangle.angled")
                        }
                    }
                    .disabled(isPreparing || isUploading)
                    .onChange(of: selectedItem) { _, newItem in
                        Task { await prepare(newItem) }
                    }
                }

                Section("Details") {
                    TextField("Description (optional)", text: $description)
                    TextField("Tags (comma-separated)", text: $tags)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }

                Section {
                    Button {
                        Task { await upload() }
                    } label: {
                        if isUploading {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                        } else {
                            Text("Submit")
                                .font(.headline)
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(selection == nil || isPreparing || isUploading)
                }
            }
            .navigationTitle("Submit Media")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .alert("Submitted!", isPresented: $uploadSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("Your submission is pending review. You'll see it in the app once approved.")
            }
        }
    }

    private func prepare(_ item: PhotosPickerItem?) async {
        selection = nil
        errorMessage = nil
        guard let item else { return }

        isPreparing = true
        defer { isPreparing = false }

        do {
            if item.supportedContentTypes.contains(where: { $0.conforms(to: .movie) }) {
                selection = try await prepareVideo(item)
            } else if let data = try await item.loadTransferable(type: Data.self) {
                // The server converts any image format, including HEIC.
                let type = item.supportedContentTypes.first
                selection = SelectedMedia(
                    data: data,
                    fileName: "upload.\(type?.preferredFilenameExtension ?? "jpg")",
                    mimeType: type?.preferredMIMEType ?? "image/jpeg",
                    isVideo: false
                )
            } else {
                errorMessage = "That item couldn't be loaded."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func prepareVideo(_ item: PhotosPickerItem) async throws -> SelectedMedia {
        guard let picked = try await item.loadTransferable(type: PickedMovie.self) else {
            throw SubmitError.unreadable
        }
        defer { try? FileManager.default.removeItem(at: picked.url) }

        // Camera videos are often hundreds of MB, so shrink them before uploading.
        let output = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("mp4")
        defer { try? FileManager.default.removeItem(at: output) }

        let asset = AVURLAsset(url: picked.url)
        guard let export = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetMediumQuality) else {
            throw SubmitError.unreadable
        }
        export.outputURL = output
        export.outputFileType = .mp4
        export.shouldOptimizeForNetworkUse = true
        await export.export()
        guard export.status == .completed else { throw SubmitError.unreadable }

        let data = try Data(contentsOf: output)
        guard data.count <= Self.maxVideoBytes else { throw SubmitError.tooLong }
        return SelectedMedia(data: data, fileName: "upload.mp4", mimeType: "video/mp4", isVideo: true)
    }

    private func upload() async {
        guard let selection else { return }

        isUploading = true
        errorMessage = nil
        defer { isUploading = false }

        do {
            var fields: [String: String] = [:]
            if !description.isEmpty { fields["description"] = description }
            if !tags.isEmpty { fields["tags"] = tags }

            let _: MediaItem = try await APIClient.shared.upload(
                path: "/parks/\(parkId)/media",
                fileData: selection.data,
                fileName: selection.fileName,
                mimeType: selection.mimeType,
                fields: fields
            )
            uploadSuccess = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct SelectedMedia {
    let data: Data
    let fileName: String
    let mimeType: String
    let isVideo: Bool
}

private enum SubmitError: LocalizedError {
    case unreadable
    case tooLong

    var errorDescription: String? {
        switch self {
        case .unreadable: return "That video couldn't be processed."
        case .tooLong: return "That video is too long. Trim it and try again."
        }
    }
}

/// Copies the picked movie somewhere we can read it after the picker's file goes away.
private struct PickedMovie: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { movie in
            SentTransferredFile(movie.url)
        } importing: { received in
            let copy = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension(received.file.pathExtension)
            try FileManager.default.copyItem(at: received.file, to: copy)
            return PickedMovie(url: copy)
        }
    }
}
