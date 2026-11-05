import CasebackProtocol
import Foundation
import SwiftUI

enum PilotFactory {
  static let service = GATTFactoryServiceUUID
  static let characteristic = GATTFactoryHandoverUUID

  static func armed(_ status: Data?) -> Bool { status == Data([1]) }

  static func credential(_ input: String) -> Data? {
    let ascii = Array(input.utf8)
    guard ascii.count == 32 else { return nil }
    func nibble(_ byte: UInt8) -> UInt8? {
      switch byte {
      case 48...57: byte - 48
      case 65...70: byte - 55
      case 97...102: byte - 87
      default: nil
      }
    }
    var result = Data(capacity: 16)
    for i in stride(from: 0, to: ascii.count, by: 2) {
      guard let a = nibble(ascii[i]), let b = nibble(ascii[i+1]) else { return nil }
      result.append((a << 4) | b)
    }
    return result
  }
}

struct PilotFactoryView: View {
  @ObservedObject var radio: PilotRadio
  @State private var token = ""
  @State private var confirming = false
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    Form {
      Section("Unidad " + radio.deviceID) {
        Text("Deja el disco sobre la base alimentada. Guarda los resultados de prueba antes de entregarlo.")
        SecureField("Código de entrega de esta unidad", text: $token)
          .textInputAutocapitalization(.never).autocorrectionDisabled()
          .privacySensitive()
        Button("Preparar entrega", role: .destructive) { confirming = true }
          .disabled(!radio.factoryAvailable || radio.busy || PilotFactory.credential(token) == nil)
      }
    }
    .navigationTitle("Entrega del taller")
    .confirmationDialog("¿Borrar las pruebas del disco y desvincular este iPhone?",
                        isPresented: $confirming, titleVisibility: .visible) {
      Button("Borrar y entregar", role: .destructive) {
        let bytes = PilotFactory.credential(token)
        token = ""
        if let bytes { radio.releaseFactoryUnit(bytes) }
        dismiss()
      }
      Button("Cancelar", role: .cancel) {}
    }
    .onDisappear { token = "" }
    .onChange(of: radio.ready) { _, ready in if !ready { token = ""; dismiss() } }
  }
}
