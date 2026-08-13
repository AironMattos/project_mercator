"use client";

import { useState } from "react";
import { X } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { GeoJsonFeatureCollection } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  territorios: GeoJsonFeatureCollection;
  selecionados: string[];
  onChange: (ids: string[]) => void;
  max: number;
};

// Seletor de 2-4 bairros (checkpoint 11c, "COMPARAÇÃO" no prompt de
// referência) - combobox pesquisável (mesmo Command/Popover já no design
// system, usado aqui pela primeira vez) mais chips removíveis dos
// selecionados, sem exigir uma tela dedicada de busca.
export function TerritorioMultiSelect({ territorios, selecionados, onChange, max }: Props) {
  const [aberto, setAberto] = useState(false);

  const nomesPorId = new Map(
    territorios.features.map((f) => [f.properties.territorio_id, f.properties.nome]),
  );

  function alternar(territorioId: string) {
    if (selecionados.includes(territorioId)) {
      onChange(selecionados.filter((id) => id !== territorioId));
    } else if (selecionados.length < max) {
      onChange([...selecionados, territorioId]);
    }
  }

  function remover(territorioId: string) {
    onChange(selecionados.filter((id) => id !== territorioId));
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {selecionados.map((id) => (
        <span
          key={id}
          className="flex items-center gap-1.5 rounded-full border border-primary bg-accent px-3 py-1 text-xs font-medium text-accent-foreground"
        >
          {nomesPorId.get(id) ?? id}
          <button
            type="button"
            onClick={() => remover(id)}
            aria-label={`Remover ${nomesPorId.get(id) ?? id}`}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}

      {selecionados.length < max && (
        <Popover open={aberto} onOpenChange={setAberto}>
          <PopoverTrigger className={buttonVariants({ variant: "outline", size: "sm" })}>
            + Adicionar bairro
          </PopoverTrigger>
          <PopoverContent className="w-72 p-0" align="start">
            <Command>
              <CommandInput placeholder="Buscar bairro…" />
              <CommandList>
                <CommandEmpty>Nenhum bairro encontrado.</CommandEmpty>
                <CommandGroup>
                  {territorios.features
                    .slice()
                    .sort((a, b) => a.properties.nome.localeCompare(b.properties.nome))
                    .map((f) => {
                      const id = f.properties.territorio_id;
                      const jaSelecionado = selecionados.includes(id);
                      return (
                        <CommandItem
                          key={id}
                          value={f.properties.nome}
                          onSelect={() => {
                            alternar(id);
                            setAberto(false);
                          }}
                          className={cn(jaSelecionado && "opacity-50")}
                        >
                          {f.properties.nome}
                        </CommandItem>
                      );
                    })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}

      <span className="text-xs text-muted-foreground">
        {selecionados.length}/{max} bairros
      </span>
    </div>
  );
}
