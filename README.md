# 📊 Dashboard Estratégico de RH - Streamlit

Este projeto é um Dashboard interativo de Recursos Humanos desenvolvido em Python, utilizando a biblioteca **Streamlit**. Ele permite a análise em tempo real de indicadores críticos como Turnover, Admissões, Desligamentos e Afastamentos.

## 🚀 Funcionalidades
- **KPIs Dinâmicos**: Visualização instantânea de Colaboradores Ativos, Admissões, Desligamentos e Taxa de Turnover conforme o mês/ano selecionado.
- **Análise de Turnover**: Gráficos de evolução mensal e anual para identificar tendências de rotatividade.
- **Filtros Personalizados**: Filtragem por **Empresa**, **Ano** e **Mês** através da barra lateral.
- **Controle de Afastamentos**: Monitoramento de colaboradores afastados sem data de retorno definida.
- **Distribuição por Unidade**: Gráfico de pizza mostrando a proporção de colaboradores por empresa.

## 📂 Estrutura de Arquivos
- `app.py`: Arquivo principal contendo a lógica de tratamento de dados e a interface do dashboard.
- `requirements.txt`: Lista de dependências necessárias (Pandas, Streamlit, Plotly, Openpyxl).
- `BI_RH.xlsx`: Base de dados em Excel (planilhas "Turn Over" e "Admitidos").

## 🛠️ Requisitos para a Base de Dados (Excel)
Para o correto funcionamento, o arquivo `BI_RH.xlsx` deve conter:
1. **Aba "Turn Over"**: Colunas `Mês_Ano`, `Admissões`, `Desligamentos` e `Colaboradores`.
2. **Aba "Admitidos"**: Colunas `EMPRESA`, `ADMISSAO`, `DTDEMISSAO` e `SITUACAO` (para identificar afastados).

## 🔧 Como Rodar Localmente
1. Clone o repositório.
2. Instale as bibliotecas:
   ```bash
   pip install -r requirements.txt
