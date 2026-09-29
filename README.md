# Limpador de Dados

Aplicativo Streamlit para limpar arquivos CSV, TXT, Excel, JSON e Parquet, em quatro etapas:

1. **Carregar**: envio do arquivo e apresentação do que o limpador faz
2. **Diagnóstico**: nulos por coluna, distribuição (histograma + boxplot com média, mediana e assimetria de Pearson), valores mais frequentes e correlação
3. **Limpeza**: as operações abaixo, organizadas em abas
4. **Resultado**: comparação antes/depois (nulos e distribuição), registro das operações e download em CSV ou Excel

Os gráficos são monocromáticos, acompanham o modo claro/escuro do sistema e têm uma tabela equivalente em "Ver dados do gráfico".

## Funcionalidades

| Seção | O que faz |
|---|---|
| Duplicatas e nulos | Remove duplicatas (por todas ou algumas colunas), linhas com nulos e colunas acima de um % de nulos |
| Texto | Remove espaços, padroniza maiúsculas/minúsculas, remove acentos e caracteres especiais, converte "NA", "null", "-" em nulo |
| Tipos e colunas | Exclui, renomeia, padroniza nomes (snake_case), converte tipos (número BR `1.234,56`, data `dd/mm/aaaa`, booleano, etc.) |
| Imputação | Média, mediana, moda, valor fixo, forward/backward fill, interpolação e **automática**, que usa a assimetria de Pearson |
| Outliers e filtros | IQR ou Z-score com remoção, winsorização ou troca por nulo, e filtros por condição |

**Imputação automática:** calcula a assimetria de Pearson `3·(média − mediana) / desvio padrão`. Se |assimetria| < limite (padrão 0,5), usa a **média**; caso contrário, usa a **mediana**. Colunas de texto usam a **moda**.

A ordem de execução é: colunas → tipos → texto → duplicatas/nulos → imputação → outliers → filtros.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Há um arquivo de teste em `exemplos/dados_sujos.csv`.

## Estrutura

- `app.py`: interface em etapas
- `cleaner.py`: leitura, diagnóstico e operações de limpeza
- `charts.py`: gráficos (Altair), agregados em Python para suportar arquivos grandes
- `.streamlit/config.toml`: tema preto e branco e barra de ferramentas oculta

## Publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub e envie os arquivos do projeto, incluindo a pasta `.streamlit/`.
2. Acesse <https://share.streamlit.io>, entre com o GitHub e clique em **Create app**.
3. Escolha o repositório e o branch, e informe `app.py` como *Main file path*.
4. Clique em **Deploy**. Em alguns minutos você recebe a URL pública.

O limite padrão de upload é de 200 MB por arquivo.
