import PhotosUI
import SwiftUI

struct ProfileView: View {
    @State private var showingLogin = false
    @State private var showingNameSetup = false
    @State private var stats: UserStats?
    @State private var editingName = false
    @State private var newName = ""
    @State private var selectedPhoto: PhotosPickerItem?
    @State private var showingPhotoPicker = false
    @State private var isUploadingAvatar = false
    @State private var confirmingDelete = false
    @State private var isDeleting = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Group {
                if AuthManager.shared.isAuthenticated {
                    signedInView
                } else {
                    signedOutView
                }
            }
            .navigationTitle("Profile")
            .sheet(isPresented: $showingLogin) {
                LoginView()
            }
        }
    }

    private var signedInView: some View {
        List {
            Section {
                HStack(spacing: 16) {
                    Button {
                        showingPhotoPicker = true
                    } label: {
                        ZStack(alignment: .bottomTrailing) {
                            Group {
                                if let user = AuthManager.shared.currentUser,
                                   let avatarUrl = user.avatarUrl,
                                   let url = URL(string: AppConfig.apiBaseURL + avatarUrl) {
                                    AsyncImage(url: url) { phase in
                                        switch phase {
                                        case .success(let image):
                                            image
                                                .resizable()
                                                .aspectRatio(contentMode: .fill)
                                        default:
                                            avatarPlaceholder
                                        }
                                    }
                                } else {
                                    avatarPlaceholder
                                }
                            }
                            .frame(width: 56, height: 56)
                            .clipShape(Circle())

                            if isUploadingAvatar {
                                Circle()
                                    .fill(.ultraThinMaterial)
                                    .frame(width: 56, height: 56)
                                ProgressView()
                            }

                            Image(systemName: "camera.circle.fill")
                                .font(.system(size: 18))
                                .foregroundStyle(.white, .gray)
                        }
                    }
                    .buttonStyle(.plain)
                    .photosPicker(isPresented: $showingPhotoPicker, selection: $selectedPhoto, matching: .images)
                    .onChange(of: selectedPhoto) { _, newItem in
                        Task { await uploadAvatar(item: newItem) }
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        if let user = AuthManager.shared.currentUser {
                            Text(user.displayName ?? user.email)
                                .font(.headline)
                                .lineLimit(1)
                            if let s = stats {
                                RankBadge(rank: s.rank)
                            }
                        }
                    }

                    Spacer()

                    Button {
                        newName = AuthManager.shared.currentUser?.displayName ?? ""
                        editingName = true
                    } label: {
                        Image(systemName: "pencil.circle")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.vertical, 8)
            }

            if let s = stats, let nextRank = s.nextRank {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(s.rank)
                                .font(.caption.weight(.semibold))
                            Spacer()
                            Text(nextRank)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                        }

                        ProgressView(value: s.progress)
                            .tint(rankColor(s.rank))

                        Text("\(s.approvedCount) / \(s.nextThreshold ?? 0) approved contributions")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            } else if let s = stats, s.rank == "Legend" {
                Section {
                    HStack {
                        RankBadge(rank: "Legend")
                        Spacer()
                        Text("\(s.approvedCount) contributions")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Section {
                NavigationLink {
                    ContributionsView()
                } label: {
                    Label("Contributions", systemImage: "photo.on.rectangle.angled")
                }

                if AuthManager.shared.currentUser?.isAdmin == true {
                    NavigationLink {
                        ReviewQueueView()
                    } label: {
                        Label("Review Queue", systemImage: "checkmark.shield")
                    }
                }
            }

            Section {
                HStack {
                    Label("Distance Unit", systemImage: "ruler")
                    Spacer()
                    Picker("", selection: Binding(
                        get: { UserSettings.shared.useMiles },
                        set: { UserSettings.shared.useMiles = $0 }
                    )) {
                        Text("mi").tag(true)
                        Text("km").tag(false)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 100)
                }

                LabeledContent("Version", value: AppConfig.appVersion)
            }

            legalSection

            Section {
                Button(role: .destructive) {
                    AuthManager.shared.logout()
                    stats = nil
                } label: {
                    Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                }

                Button(role: .destructive) {
                    confirmingDelete = true
                } label: {
                    if isDeleting {
                        ProgressView()
                    } else {
                        Label("Delete Account", systemImage: "trash")
                    }
                }
                .disabled(isDeleting)
            }
        }
        .alert("Delete your account?", isPresented: $confirmingDelete) {
            Button("Delete Forever", role: .destructive) {
                Task { await deleteAccount() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This permanently deletes your account, favorites, photos and videos. It can't be undone.")
        }
        .alert(errorMessage ?? "", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("OK") {}
        }
        .task {
            await AuthManager.shared.fetchUser()
            await loadStats()
            checkNameSetup()
        }
        .sheet(isPresented: $showingNameSetup) {
            NameSetupView()
        }
        .alert("Edit Name", isPresented: $editingName) {
            TextField("Name", text: $newName)
                .onChange(of: newName) { _, val in
                    let filtered = String(val.filter { $0.isLetter || $0.isNumber }.prefix(20))
                    if filtered != val { newName = filtered }
                }
            Button("Save") {
                Task { await saveName() }
            }
            Button("Cancel", role: .cancel) {}
        }
    }

    private var signedOutView: some View {
        List {
            Section {
                VStack(spacing: 20) {
                    Image(systemName: "person.circle")
                        .font(.system(size: 64))
                        .foregroundStyle(.secondary)
                        .frame(height: 70)

                    Text("Not signed in")
                        .font(.headline)

                    Button("Sign In") {
                        showingLogin = true
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.black)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
            }

            legalSection
        }
    }

    private var legalSection: some View {
        Section {
            Link("Terms of Service", destination: AppConfig.termsURL)
            Link("Privacy Policy", destination: AppConfig.privacyURL)
            Link("Park data © OpenStreetMap contributors", destination: AppConfig.osmCopyrightURL)
        }
        .foregroundStyle(.primary)
    }

    private var avatarPlaceholder: some View {
        Image(systemName: "person.circle.fill")
            .resizable()
            .foregroundStyle(.secondary)
    }

    private func rankColor(_ rank: String) -> Color {
        switch rank {
        case "Legend": return .yellow
        case "Wizard": return .purple
        case "Pro": return .blue
        default: return .gray
        }
    }

    private func loadStats() async {
        stats = try? await APIClient.shared.request(.myStats)
    }

    private func checkNameSetup() {
        if let user = AuthManager.shared.currentUser,
           user.displayName == nil || user.displayName?.isEmpty == true {
            showingNameSetup = true
        }
    }

    private func saveName() async {
        let trimmed = newName.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        do {
            let _: User = try await APIClient.shared.request(.updateMe(displayName: trimmed))
            await AuthManager.shared.fetchUser()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func uploadAvatar(item: PhotosPickerItem?) async {
        guard let item else { return }

        isUploadingAvatar = true
        defer { isUploadingAvatar = false }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else { return }
            let _: User = try await APIClient.shared.upload(
                path: "/user/me/avatar",
                fileData: data,
                fileName: "avatar.jpg",
                mimeType: "image/jpeg"
            )
            await AuthManager.shared.fetchUser()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func deleteAccount() async {
        isDeleting = true
        defer { isDeleting = false }

        do {
            try await APIClient.shared.send(.deleteAccount)
            AuthManager.shared.logout()
            stats = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    ProfileView()
}
