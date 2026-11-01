import SwiftUI

struct ParkPill: View {
    let icon: String
    let text: String
    var inverted: Bool = false

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
            Text(text)
        }
        .font(.caption.weight(.medium))
        .foregroundStyle(inverted ? .white : .primary)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(inverted ? Color.primary : Color(.systemGray6), in: Capsule())
    }
}
