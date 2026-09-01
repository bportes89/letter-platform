"use client";

import { ChangeEvent, InputHTMLAttributes } from "react";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function digitsToAmount(digits: string): string {
  if (!digits) return "";
  return (Number(digits) / 100).toString();
}

type CurrencyInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: string;
  onChange: (amount: string) => void;
};

export function CurrencyInput({ value, onChange, ...props }: CurrencyInputProps) {
  const cents = value && Number(value) > 0 ? Math.round(Number(value) * 100) : 0;
  const display = cents > 0 ? brl.format(cents / 100) : "";

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const digits = e.target.value.replace(/\D/g, "");
    onChange(digits ? digitsToAmount(digits) : "");
  }

  return (
    <input
      type="text"
      inputMode="numeric"
      autoComplete="off"
      value={display}
      onChange={handleChange}
      {...props}
    />
  );
}
