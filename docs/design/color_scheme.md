# prudentIA – Esquema de Cores

Baseado no tom principal **#FFC145** (dourado/âmbar). O objetivo é transmitir confiança, inovação e proximidade, mantendo acessibilidade e contraste adequados.

---

## 1. Paleta Principal

| Função | Nome | HEX | RGB | Uso sugerido |
|--------|------|-----|-----|--------------|
| Primária | Golden Sun | **#FFC145** | 255 ,193 ,69 | Botões primários, ícones de ação, realces |
| Complementar | Prudent Blue | **#45A2FF** | 69 ,162 ,255 | Links, botões secundários, estados ativos |
| Neutro escuro | Midnight Ink | **#1E2025** | 30 ,32 ,37 | Texto principal, cabeçalhos, fundo do header |
| Neutro claro | Cloud Mist | **#F7F8FA** | 247 ,248 ,250 | Fundo geral, cartões, tabelas alternadas |
| Acento de sucesso | Emerald Trust | **#27C28B** | 39 ,194 ,139 | Mensagens de sucesso, indicadores positivos |
| Acento de alerta | Sunset Coral | **#FF6A55** | 255 ,106 ,85 | Erros, avisos críticos |
| Acento de info | Sky Wave | **#4AC8FF** | 74 ,200 ,255 | Notificações informativas |

Complementar foi calculada girando 180° no círculo cromático (#FFC145 → #45A2FF).

---

## 2. Variações de Tons

| Tom | 90 % | 70 % | 50 % | 30 % | 10 % |
|-----|------|------|------|------|------|
| Golden Sun | #E6AD3E | #CC972E | #B3821F | #996C10 | #7F5600 |
| Prudent Blue | #3E92E6 | #377FCC | #306DB3 | #295A99 | #224880 |

> Percentual indica a **luminosidade** original preservada, útil para hovers, estados desativados e bordas.

---

## 3. Exemplo de Aplicação na Interface

| Componente | Cor principal | Estado hover/active | Texto/Ícone |
|------------|---------------|---------------------|-------------|
| Botão Primário | Golden Sun 100 % | Golden Sun 70 % | Cloud Mist |
| Botão Secundário | Prudent Blue 100 % | Prudent Blue 70 % | Cloud Mist |
| Barra de Navegação | Midnight Ink | – | Cloud Mist / Golden Sun (ícone ativo) |
| Fundo de Cartão | Cloud Mist | Cloud Mist 90 % | Midnight Ink |
| Notificação Sucesso | Emerald Trust 100 % | Emerald Trust 70 % | Cloud Mist |
| Notificação Erro | Sunset Coral 100 % | Sunset Coral 70 % | Cloud Mist |

---

## 4. Acessibilidade & Contraste

- Certifique-se de que o contraste entre **Golden Sun (#FFC145)** e texto **Midnight Ink (#1E2025)** atinge AA (≥ 4.5 : 1) para tamanhos de corpo.
- Para fundos claros, use textos em **Midnight Ink**; para fundos escuros, use **Cloud Mist**.
- Utilize as variações de tons mais escuras quando necessário para cumprir requisitos de contraste.

---

## 5. Tokens de Design (CSS/SCSS)

```scss
:root {
  --color-primary: #FFC145;
  --color-primary-dark: #CC972E;
  --color-primary-light: #FFE5A6;

  --color-secondary: #45A2FF;
  --color-secondary-dark: #377FCC;

  --color-bg: #F7F8FA;
  --color-surface: #FFFFFF;

  --color-text: #1E2025;
  --color-text-light: #5A5D65;

  --color-success: #27C28B;
  --color-error: #FF6A55;
  --color-info: #4AC8FF;
}
```

Esses tokens facilitam a implementação consistente no front-end (React, Django templates, etc.).

---

### Próximos Passos
1. Integrar o esquema no framework CSS (Tailwind, Bootstrap custom, ou estilo próprio).
2. Criar componentes de UI reutilizáveis (Button, Card, Alert) usando as cores definidas.
3. Executar testes de contraste com usuários para ajustes finos. 
