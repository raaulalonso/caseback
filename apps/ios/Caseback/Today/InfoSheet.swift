import SwiftUI

/// The explanation behind a chart's "i": what it shows, then how to read it. A small sheet, so the chart stays in view.
struct InfoSheet: View {
    var destination: TodayDestination
    /// A third paragraph for the context the chart is shown in (Trends: the usual range).
    var extra: String?
    /// The small print: how far to trust it. Last, quiet, in `text3`.
    var fine: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s16) {
            HStack(spacing: Space.s12) {
                MetricMarkShape(metric: destination.metric, size: 20)
                Text(destination.title).font(.system(size: 22, weight: .semibold)).foregroundStyle(Palette.text1)
            }
            Text(L("today.info.\(destination.infoKey).what"))
                .font(.system(size: 17)).foregroundStyle(Palette.text1)
                .fixedSize(horizontal: false, vertical: true)
            Text(L("today.info.\(destination.infoKey).read"))
                .font(.system(size: 15)).foregroundStyle(Palette.text2)
                .fixedSize(horizontal: false, vertical: true)
            if let extra {
                Text(extra).font(.system(size: 15)).foregroundStyle(Palette.text2).fixedSize(horizontal: false, vertical: true)
            }
            if let fine {
                Text(fine).font(.system(size: 13)).foregroundStyle(Palette.text3).fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Space.s8)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, Space.margin)
        .padding(.top, Space.s32)
        .frame(maxWidth: .infinity, alignment: .leading)
        .presentationDetents([.height((extra == nil ? 300 : 400) + (fine == nil ? 0 : 130)), .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Palette.tile)
        .presentationCornerRadius(Radius.hero)
    }
}
