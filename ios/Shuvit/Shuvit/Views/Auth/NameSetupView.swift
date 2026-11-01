import SwiftUI

struct NameSetupView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()

                VStack(spacing: 12) {
                    Image(systemName: "person.text.rectangle")
                        .font(.system(size: 48))
                        .foregroundStyle(.primary)

                    Text("What should we call you?")
                        .font(.title2.weight(.bold))

                    Text("Pick a name for your profile")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                TextField("Name", text: $name)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.name)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .padding(.horizontal, 32)
                    .onChange(of: name) { _, newValue in
                        let filtered = String(newValue.filter { $0.isLetter || $0.isNumber }.prefix(20))
                        if filtered != newValue { name = filtered }
                    }

                Button {
                    Task { await save() }
                } label: {
                    Group {
                        if isLoading {
                            ProgressView()
                        } else {
                            Text("Continue")
                        }
                    }
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .tint(.black)
                .padding(.horizontal, 32)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)

                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }

                Spacer()
            }
            .interactiveDismissDisabled()
        }
    }

    private func save() async {
        isLoading = true
        errorMessage = nil
        do {
            let _: User = try await APIClient.shared.request(
                .updateMe(displayName: name.trimmingCharacters(in: .whitespaces))
            )
            await AuthManager.shared.fetchUser()
            dismiss()
        } catch let error as APIError {
            if case .serverError(409, _) = error {
                errorMessage = "That name is already taken"
            } else {
                errorMessage = error.localizedDescription
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
