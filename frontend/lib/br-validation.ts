const digitsOnly = (value: string) => value.replace(/\D/g, "");

export function isValidEmail(value: string): boolean {
  const text = value.trim();
  if (!text || text.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text);
}

export function isValidPhoneBr(value: string): boolean {
  const d = digitsOnly(value);
  return d.length === 10 || d.length === 11;
}

function cpfChecksum(nums: number[], factor: number): number {
  const total = nums.reduce((sum, n, i) => sum + n * (factor - i), 0);
  const rest = (total * 10) % 11;
  return rest === 10 ? 0 : rest;
}

export function isValidCpf(value: string): boolean {
  const d = digitsOnly(value);
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  const nums = d.split("").map(Number);
  if (cpfChecksum(nums.slice(0, 9), 10) !== nums[9]) return false;
  if (cpfChecksum(nums.slice(0, 10), 11) !== nums[10]) return false;
  return true;
}

function cnpjChecksum(nums: number[], weights: number[]): number {
  const total = nums.reduce((sum, n, i) => sum + n * weights[i], 0);
  const rest = total % 11;
  return rest < 2 ? 0 : 11 - rest;
}

export function isValidCnpj(value: string): boolean {
  const d = digitsOnly(value);
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const nums = d.split("").map(Number);
  const w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const w2 = [6, ...w1];
  if (cnpjChecksum(nums.slice(0, 12), w1) !== nums[12]) return false;
  if (cnpjChecksum(nums.slice(0, 13), w2) !== nums[13]) return false;
  return true;
}

export function isValidCpfOrCnpj(value: string): boolean {
  const d = digitsOnly(value);
  if (d.length === 11) return isValidCpf(d);
  if (d.length === 14) return isValidCnpj(d);
  return false;
}

export function validationMessageForPerson(document: string, email: string, phone: string): string | null {
  if (!isValidCpfOrCnpj(document)) return "CPF ou CNPJ inválido.";
  if (!isValidEmail(email)) return "E-mail inválido.";
  if (!isValidPhoneBr(phone)) return "Telefone inválido (10 ou 11 dígitos).";
  return null;
}
