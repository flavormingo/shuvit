import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct SubmitMediaSheet: View {
    let parkId: UUID
    @Environment(\.dismiss) private var dismiss

    @State private var selectedItem: PhotosPickerItem?
    @State private var selection: SelectedPhoto?
    @State private var isPreparing = false
    @State private var description = ""
    @State private var tags = ""
    @State private var isUploading = false
    @State private var errorMessage: String?
    @State private var uploadSuccess = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Select Photo") {
                    PhotosPicker(selection: $selectedItem, matching: .images) {
                        if isPreparing {
                            Label("Preparing…", systemImage: "hourglass")
                        } else if selection != nil {
                            Label("Photo selected", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        } else {
                            Label("Choose photo", systemImage: "photo.on.rectangle.angled")
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
            .navigationTitle("Add Photo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .alert("Submitted!", isPresented: $uploadSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("Your photo is pending review. You'll see it in the app once approved.")
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
            if let data = try await item.loadTransferable(type: Data.self) {
                let type = item.supportedContentTypes.first
                selection = SelectedPhoto(
                    data: data,
                    fileName: "upload.\(type?.preferredFilenameExtension ?? "jpg")",
                    mimeType: type?.preferredMIMEType ?? "image/jpeg"
                )
            } else {
                errorMessage = "That photo couldn't be loaded."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
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

private struct SelectedPhoto {
    let data: Data
    let fileName: String
    let mimeType: String
}
