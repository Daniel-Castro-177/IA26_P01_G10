# Ajuda — IA26_P01_G10

Guia rápido para arrancar, testar e usar o projeto.

## 1. Arrancar o projeto

Na pasta do projeto:

```bash
python3 -m venv .venv              # criar o ambiente virtual (só da primeira vez)
source .venv/bin/activate          # ativar (Windows: .venv\Scripts\activate)
pip install -r requirements.txt    # instalar pandas, numpy, matplotlib e jupyter
jupyter notebook                   # abrir o notebook IA26_P01_G10.ipynb
```

> Corre sempre os comandos a partir da **raiz do projeto**: o `model.py` lê os CSV de `data/...` com caminhos relativos.

## 2. Estrutura

| Ficheiro / pasta | O que é |
|---|---|
| `IA26_P01_G10.ipynb` | Notebook principal (relatório + código) |
| `model.py` | Modelação: classes `Problem`, `Request`, `Vehicle`, `State`, verificador, custo e espaço de estados |
| `test_model.py` | Testes com rotas escritas à mão |
| `data/data_tiny_30_31oct2026/` | Dataset pequeno (40 pedidos, 2 veículos) |
| `data/data_small_30_31oct2026/` | Dataset maior (80 pedidos, 2 veículos) |
| `readme.txt` | Link do repositório (obrigatório na entrega) |

## 3. Testar

```bash
python -m unittest test_model -v
```

Deve aparecer `OK` no fim. Os testes verificam rotas válidas (um veículo e dois veículos)
e rotas inválidas (capacidade, janelas, local errado, saltar o armazém, pedidos em falta ou
repetidos, mais de 24 h no armazém, etc.).

## 4. Como o problema está modelado

- **Pedido (`Request`)** = uma linha de `order_items.csv`. Tem peso, local de recolha (produtor),
  local de entrega (cliente) e duas janelas `(início, fim)`: `recolha` e `entrega`.
- Cada pedido passa por **4 paragens**: `recolha` no produtor → `descarga` no armazém →
  `carga` no armazém → `entrega` no cliente. A recolha e a entrega podem ser feitas por veículos
  diferentes.
- **Paragem** = tuplo `(tipo, local, pedidos)`, ex.: `("recolha", 1, (31, 5))`.
- **Solução** = dicionário `{id_veiculo: [paragem, paragem, ...]}`. Os veículos saem e voltam ao
  armazém (não é preciso escrever isso na rota).
- **Tempos** em minutos desde 30/10 00:00. As janelas são para o **início** do serviço; se o
  veículo chega cedo, espera.
- **Regras** (de `rules.csv`): 10 min por recolha/entrega, 15 min para descarregar e 15 para
  carregar, máximo 24 h no armazém, horizonte de 2 dias.
- **Custo** = km totais.

## 5. Usar o `model.py`

### Carregar um dataset

```python
from model import Problem, PASTA_TINY, PASTA_SMALL

p = Problem(PASTA_TINY)           # ou Problem(PASTA_SMALL)
p.pedidos[30].peso                # 3.8
p.pedidos[30].recolha             # (480.0, 630.0)  -> 30/10 08:00 a 10:30
p.veiculos[0].capacidade          # 150.0
p.km(4, 8), p.tempo(4, 8)         # distância (km) e tempo (min) entre dois locais
```

### Escrever uma rota à mão e verificá-la

```python
rota = [p.recolha(31), p.recolha(30), p.descarga(30, 31), p.carga(30, 31), p.entrega(30, 31)]

valida, erros, km, horarios = p.verificar({1: rota}, pedidos=[30, 31])
print(valida, round(km, 1))       # True 134.6
print(erros)                      # [] (ou a lista de problemas encontrados)
```

- `pedidos=[...]` indica os pedidos que **têm** de ser servidos. Sem esse argumento, são
  obrigatórios **todos** (é o que se usa para validar uma solução final).
- `horarios[id_veiculo]` é uma lista de `(paragem, chegada, início, fim)` por paragem.

### Custo de uma solução

```python
p.custo({1: rota})                # km + 1000 por cada erro
```

A penalização deixa a procura local comparar soluções que ainda não são válidas.

### Espaço de estados (para Greedy / A*)

```python
s = p.estado_inicial()
acoes = p.acoes(s)                # lista de (indice_veiculo, paragem)
s2 = p.resultado(s, acoes[0])     # novo estado
p.custo_passo(s, acoes[0])        # km dessa ação
p.objetivo(s2)                    # True quando tudo foi entregue e os veículos voltaram
p.solucao(s2)                     # rotas do estado -> {id_veiculo: [paragens]}
```

- `State` tem `__eq__` e `__hash__`, por isso pode ir para `set`/`dict` (lista de visitados) e tem
  `__lt__` para o `heapq` não falhar em empates.
- As ações já cortam estados sem saída (pedidos que já não chegam a tempo), por isso
  `acoes()` devolve `[]` nesses casos.
- `Problem(PASTA_TINY, so_o_mais_atrasado=True)` faz com que, em cada estado, só se mexa o
  veículo com o tempo mais baixo. A procura fica muito mais rápida, mas pode perder a melhor
  solução (no tiny, com uma DFS simples: 302 nós / 859 km contra 999 nós / 684 km).

### Esqueleto de um A*

```python
import heapq

def a_estrela(p, h):
    s0 = p.estado_inicial()
    fila = [(h(s0), 0, s0)]
    visitados = set()
    expandidos = 0
    while fila:
        f, g, s = heapq.heappop(fila)
        if p.objetivo(s):
            return s, expandidos
        if s in visitados:
            continue
        visitados.add(s)
        expandidos += 1
        for a in p.acoes(s):
            s2 = p.resultado(s, a)
            g2 = g + p.custo_passo(s, a)
            heapq.heappush(fila, (g2 + h(s2), g2, s2))
    return None, expandidos

# exemplo de heurística (trivial): h = 0  -> equivale a custo uniforme
estado, nos = a_estrela(p, lambda s: 0)
```

Para o Greedy usa só `h(s2)` como prioridade em vez de `g2 + h(s2)`.

> Atenção: com `h = 0` o A* não termina em tempo útil, nem no tiny (testado: mais de 20 000 nós
> expandidos sem chegar ao objetivo, mesmo com `so_o_mais_atrasado=True`). É por isso que são
> precisas boas heurísticas (ex.: km que ainda faltam até aos produtores/clientes pendentes,
> nº de paragens em falta) e, se necessário, um limite de nós.

## 6. Entrega (resumo do guia do professor)

- Repositório GitHub **privado** `IA26_P01_G10`, com o professor como colaborador.
- ZIP `IA_P01_G10.zip` no Moodle com o código, o notebook, o `readme.txt` e a pasta `data/`.
- Falta fazer: `01_eda_tiny.ipynb`, Greedy + A* (2 heurísticas, nós expandidos), Hill-Climbing
  (curvas custo vs. iteração), CSP (variáveis, domínios, restrições, nº de backtracks),
  análise de resultados e conclusão.
