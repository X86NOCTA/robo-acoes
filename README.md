# 𓂀 HORUS — o olho que vê o mercado

Programa para Ubuntu (Linux) que, todo dia depois do fechamento da bolsa, mostra em português simples:

- 🟢 quais ações **comprar** amanhã (quantidade, preço máximo e preço de proteção)
- 🔴 quais **vender**
- 🟡 quais **manter**
- 💼 **Minha carteira**: suas compras e vendas, gráficos de ganho/perda e imposto de renda estimado

Você manda as ordens à mão pelo app da sua corretora (qualquer corretora).

## Instalar (ou atualizar) num computador com Ubuntu

1. Aperte **Ctrl + Alt + T** para abrir o Terminal.
2. Cole este comando e aperte Enter:

```bash
wget -qO- https://raw.githubusercontent.com/X86NOCTA/robo-acoes/main/instalar.sh | bash
```

Pronto: o robô abre no navegador. Nas próximas vezes, procure **"Horus"** no menu de aplicativos.

> Suas operações e configurações ficam só no computador onde você usa (não vão para o GitHub).
> Para levar para outro computador: aba **Minha carteira** → **Salvar cópia das operações**, e lá → **Carregar cópia**.

## Instalar (ou atualizar) no Windows 10/11

1. Aperte a tecla **Windows**, digite **PowerShell** e aperte Enter.
2. Cole este comando e aperte Enter:

```powershell
irm https://raw.githubusercontent.com/X86NOCTA/robo-acoes/main/instalar.ps1 | iex
```

Se o computador não tiver Python, o instalador instala sozinho. No fim, aparece o atalho **Horus** na Área de Trabalho e no menu Iniciar.

## Atualizar

Clique em **⬆️ Atualizar o robô** no canto de cima do programa.

## Aviso

O robô segue regras que funcionaram no passado. Isso não garante lucro. Use só dinheiro que você pode perder.
Não é recomendação de investimento. Cotações gratuitas, com atraso.
