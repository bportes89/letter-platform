import { ShieldCheck } from "lucide-react";

export function ValidStamp({code,hash}:{code:string;hash:string}){
 return <div className="valid-stamp" role="img" aria-label={`Registro de evidência Valid-Stamp ${code}`}>
  <div className="valid-stamp-ring"><ShieldCheck/><strong>VALID</strong><span>STAMP</span></div>
  <small>{code} · {hash.slice(0,12)}</small>
 </div>
}
