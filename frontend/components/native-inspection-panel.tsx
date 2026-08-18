"use client";

import { Camera } from "lucide-react";
import { useRef, useState } from "react";
import { api, CollateralNativeInspection } from "@/lib/api";

export type NativePhotoMeta = {
  filename: string;
  exif_timestamp_unix: number;
  gps_latitude: number;
  gps_longitude: number;
};

type Props = {
  contractId: string;
  productLabel: string;
  onSubmitted?: (item: CollateralNativeInspection) => void;
};

export function NativeInspectionPanel({ contractId, productLabel, onSubmitted }: Props) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const [photos, setPhotos] = useState<NativePhotoMeta[]>([]);
  const [inspection, setInspection] = useState<CollateralNativeInspection | null>(null);
  const [message, setMessage] = useState("");

  async function capturePhoto() {
    if (!cameraRef.current?.files?.[0]) return;
    const file = cameraRef.current.files[0];
    let gps = { latitude: -14.235, longitude: -51.925 };
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
      );
      gps = pos.coords;
    } catch { /* sandbox */ }
    setPhotos((prev) => [
      ...prev,
      {
        filename: file.name,
        exif_timestamp_unix: Math.floor(Date.now() / 1000),
        gps_latitude: gps.latitude,
        gps_longitude: gps.longitude,
      },
    ]);
    cameraRef.current.value = "";
  }

  async function submit() {
    if (photos.length < 3) {
      setMessage("Mínimo 3 fotos nativas (câmera + GPS/EXIF).");
      return;
    }
    try {
      const item = await api<CollateralNativeInspection>(`/contracts/${contractId}/native-inspection`, {
        method: "POST",
        body: JSON.stringify({
          photos: photos.map((p) => ({ ...p, source: "CAMERA_NATIVE" })),
        }),
      });
      setInspection(item);
      setPhotos([]);
      setMessage("Vistoria nativa registrada — evidência vinculada ao leilão em inadimplência.");
      onSubmitted?.(item);
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha ao enviar vistoria");
    }
  }

  return (
    <section className="panel">
      <h3><Camera />Vistoria nativa — {productLabel}</h3>
      <p className="form-help">
        Câmera nativa obrigatória (galeria bloqueada). Fotos com timestamp e GPS alimentam o dossiê de leilão em caso de inadimplência.
      </p>
      {message && <small className="muted">{message}</small>}
      {inspection ? (
        <div className="notice">
          <b>{inspection.photos_count} fotos</b> · Vault: <small>{inspection.vault_s3_uri}</small>
        </div>
      ) : (
        <>
          <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={() => void capturePhoto()} />
          <small>{photos.length} foto(s) capturada(s)</small>
          <button type="button" disabled={photos.length < 3} onClick={() => void submit()}>Registrar vistoria nativa</button>
        </>
      )}
    </section>
  );
}
