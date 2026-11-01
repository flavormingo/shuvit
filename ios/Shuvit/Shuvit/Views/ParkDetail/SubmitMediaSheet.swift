import PhotosUI
import SwiftUI

struct SubmitMediaSheet: View {
    let parkId: UUID
    @Environment(\.dismiss) private var dismiss

    @State private var selectedItem: PhotosPickerItem?
    @State private var selectedImageData: Data?
    @State private var description = ""
    @State private var tags = ""
    @State private var isUploading = false
    @State private var errorMessage: String?
    @State private var uploadSuccess = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Select Media") {
                    PhotosPicker(selection: $selectedItem, matching: .any(of: [.images, .videos])) {
                        if selectedImageData != nil {
                            Label("Media selected", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        } else {
                            Label("Choose photo or video", systemImage: "photo.on.rectangle.angled")
                        }
                    }
                    .onChange(of: selectedItem) { _, newItem in
                        Task {
                            if let data = try? await newItem?.loadTransferable(type: Data.self) {
                                selectedImageData = data
                            }
                        }
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
                    .disabled(selectedImageData == nil || isUploading)
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

    private func upload() async {
        guard let data = selectedImageData else { return }

        isUploading = true
        errorMessage = nil

        do {
            var fields: [String: String] = [:]
            if !description.isEmpty { fields["description"] = description }
            if !tags.isEmpty { fields["tags"] = tags }

            let _: MediaItem = try await APIClient.shared.upload(
                path: "/parks/\(parkId)/media",
                fileData: data,
                fileName: "upload.jpg",
                mimeType: "image/jpeg",
                fields: fields
            )
            uploadSuccess = true
        } catch {
            errorMessage = error.localizedDescription
        }

        isUploading = false
    }
}
