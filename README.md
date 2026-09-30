# Limpador de Dados

Aplicativo Streamlit para limpar arquivos CSV, TSV, TXT, Excel, JSON e Parquet em três etapas:

1. **Carregar**: arraste o arquivo (separador e planilha podem ser ajustados depois, no ícone de opções do cartão do arquivo)
2. **Tratar**: painel com qualidade antes → depois, substituições manuais, completude por coluna, gráficos e um card por coluna com a estratégia de tratamento
3. **Exportar**: indicadores, log de alterações, gráficos de antes e depois, tabela com as células imputadas destacadas e download em CSV, Excel ou JSON

## Funcionalidades

| Onde | O que faz |
|---|---|
| Detecção de tipo | Identifica cada coluna como numérica, categórica, booleana, data ou texto (inclui número BR `1.234,56`, datas `dd/mm/aaaa` e VERDADEIRO/FALSO, sim/não). O tipo pode ser trocado no menu ⋮ do card |
| Substituições manuais | Escolha a coluna (ou todas), selecione um valor existente ou digite, e defina o novo valor. Modos exato, contém e regex, com opção de diferenciar maiúsculas. Substituir por vazio vira nulo |
| Deduplicação automática | Remove linhas repetidas (pode ser desligada em *Mais opções*) |
| Imputação por coluna | Média, mediana, moda, anterior (forward fill), seguinte (backward fill), interpolação ou preservar. A sugestão inicial usa a assimetria de Pearson |
| Outliers por IQR | Manter, limitar ao intervalo, tornar nulo ou remover a linha, por coluna |
| Gráficos | Nulos por coluna, distribuição (histograma + boxplot), valores mais frequentes, correlação e comparações antes/depois |
| Mais opções | Maiúsculas/minúsculas, acentos, caracteres especiais, excluir e renomear colunas, remover linhas com nulos, fator IQR, limite de assimetria e filtros por condição |

**Sugestão de imputação:** calcula a assimetria de Pearson `3·(média − mediana) / desvio padrão`. Se |assimetria| < limite (padrão 0,5), sugere a **média**; caso contrário, a **mediana**. Colunas categóricas e booleanas usam a **moda**, datas repetem o valor anterior e texto livre é preservado.

A ordem de execução é: colunas → texto → substituições manuais → tipos → duplicatas → linhas com nulos → outliers → imputação → filtros.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Há um arquivo de teste em `exemplos/dados_sujos.csv`.

## Estrutura

- `app.py`: interface em etapas (Carregar, Tratar, Exportar)
- `cleaner.py`: leitura, detecção de tipo, diagnóstico e operações de limpeza
- `charts.py`: gráficos (Altair), agregados em Python para suportar arquivos grandes
- `.streamlit/config.toml`: tema escuro e barra de ferramentas oculta

## Publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub e envie os arquivos do projeto, incluindo a pasta `.streamlit/`.
2. Acesse <https://share.streamlit.io>, entre com o GitHub e clique em **Create app**.
3. Escolha o repositório e o branch, e informe `app.py` como *Main file path*.
4. Clique em **Deploy**. Em alguns minutos você recebe a URL pública.

O limite padrão de upload é de 200 MB por arquivo.
