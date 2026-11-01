import AVKit
import SwiftUI

struct ReviewQueueView: View {
    @State private var items: [ReviewItem] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if isLoading {
                ProgressView()
            } else if items.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "checkmark.seal")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary)
                    Text("All caught up")
                        .font(.headline)
                }
            } else {
                List(items) { item in
                    row(item)
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("Review Queue")
        .task { await load() }
        .refreshable { await load() }
        .alert(errorMessage ?? "", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("OK") {}
        }
    }

    private func row(_ item: ReviewItem) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if item.reportCount > 0 {
                Label("Reported \(item.reportCount) time\(item.reportCount == 1 ? "" : "s")", systemImage: "flag.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.red)
            }

            Text(item.parkName)
                .font(.headline)

            preview(item)
                .frame(maxWidth: .infinity)
                .frame(height: 260)
                .clipShape(RoundedRectangle(cornerRadius: 10))

            Text("By \(item.contributorName ?? "unnamed user")")
                .font(.caption)
                .foregroundStyle(.secondary)

            if let description = item.description, !description.isEmpty {
                Text(description)
                    .font(.subheadline)
            }

            HStack(spacing: 10) {
                decisionButton(item, approve: false)
                decisionButton(item, approve: true)
            }
        }
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private func preview(_ item: ReviewItem) -> some View {
        if item.mediaType == "video", let url = item.fullFileURL {
            VideoPlayer(player: AVPlayer(url: url))
        } else {
            AsyncImage(url: item.fullFileURL) { phase in
                switch phase {
                case .success(let image):
                    image.resizable().aspectRatio(contentMode: .fit)
                case .failure:
                    Image(systemName: "photo").foregroundStyle(.secondary)
                default:
                    ProgressView()
                }
            }
        }
    }

    private func decisionButton(_ item: ReviewItem, approve: Bool) -> some View {
        Button {
            Task { await decide(item, approve: approve) }
        } label: {
            Text(approve ? "Approve" : "Reject")
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
        }
        .buttonStyle(.borderedProminent)
        .tint(approve ? .green : .red)
    }

    private func load() async {
        defer { isLoading = false }
        do {
            items = try await APIClient.shared.request(.reviewQueue)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func decide(_ item: ReviewItem, approve: Bool) async {
        do {
            try await APIClient.shared.send(.reviewMedia(id: item.id, approve: approve))
            items.removeAll { $0.id == item.id }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
