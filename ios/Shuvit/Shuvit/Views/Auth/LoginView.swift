import SwiftUI

struct LoginView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var viewModel = AuthViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()

                VStack(spacing: 12) {
                    Image("ShuvitLogo")
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(height: 80)

                    Text("Shuvit")
                        .font(.largeTitle.weight(.bold))

                    Text("Sign in to save favorites\nand submit media")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }

                if viewModel.codeSent {
                    otpEntryView
                } else {
                    emailEntryView
                }

                Spacer()

                VStack(spacing: 6) {
                    Text("No password needed. We'll send you a code.")
                        .foregroundStyle(.tertiary)

                    Text("By continuing you agree to our [Terms](\(AppConfig.termsURL.absoluteString)), including no objectionable content, and [Privacy Policy](\(AppConfig.privacyURL.absoluteString)).")
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }
                .font(.caption)
                .padding(.bottom, 16)
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .onChange(of: AuthManager.shared.isAuthenticated) { _, authenticated in
                if authenticated { dismiss() }
            }
        }
    }

    private var emailEntryView: some View {
        VStack(spacing: 16) {
            TextField("Email address", text: $viewModel.email)
                .textFieldStyle(.roundedBorder)
                .textContentType(.emailAddress)
                .keyboardType(.emailAddress)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
                .padding(.horizontal, 32)

            Button {
                Task { await viewModel.sendCode() }
            } label: {
                Group {
                    if viewModel.isLoading {
                        ProgressView()
                    } else {
                        Text("Send Code")
                    }
                }
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(.black)
            .padding(.horizontal, 32)
            .disabled(viewModel.isLoading)

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
    }

    private var otpEntryView: some View {
        VStack(spacing: 20) {
            VStack(spacing: 8) {
                Image(systemName: "envelope.badge.fill")
                    .font(.system(size: 36))
                    .foregroundStyle(.green)

                Text("Enter the 6-digit code")
                    .font(.headline)

                Text("Sent to \(viewModel.email)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            OTPFieldView(code: $viewModel.otpCode, onComplete: {
                Task { await viewModel.verifyCode() }
            })
            .padding(.horizontal, 32)

            Button {
                Task { await viewModel.verifyCode() }
            } label: {
                Group {
                    if viewModel.isLoading {
                        ProgressView()
                    } else {
                        Text("Verify")
                    }
                }
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(.black)
            .padding(.horizontal, 32)
            .disabled(viewModel.otpCode.count < 6 || viewModel.isLoading)

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            Button {
                viewModel.codeSent = false
                viewModel.otpCode = ""
                viewModel.errorMessage = nil
            } label: {
                Text("Use a different email")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct OTPFieldView: View {
    @Binding var code: String
    var onComplete: () -> Void

    @FocusState private var isFocused: Bool

    var body: some View {
        ZStack {
            TextField("", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .focused($isFocused)
                .opacity(0)
                .onChange(of: code) { _, newValue in
                    let filtered = String(newValue.filter(\.isNumber).prefix(6))
                    if filtered != newValue {
                        code = filtered
                    }
                    if filtered.count == 6 {
                        onComplete()
                    }
                }

            HStack(spacing: 8) {
                ForEach(0..<6, id: \.self) { index in
                    let digit = index < code.count
                        ? String(code[code.index(code.startIndex, offsetBy: index)])
                        : ""

                    Text(digit)
                        .font(.system(size: 28, weight: .bold, design: .monospaced))
                        .frame(width: 46, height: 56)
                        .background(
                            RoundedRectangle(cornerRadius: 10)
                                .fill(Color(.systemGray6))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(
                                    index == code.count && isFocused
                                        ? Color.black
                                        : Color.clear,
                                    lineWidth: 2
                                )
                        )
                }
            }
            .contentShape(Rectangle())
            .onTapGesture {
                isFocused = true
            }
        }
        .onAppear { isFocused = true }
    }
}

#Preview {
    LoginView()
}
