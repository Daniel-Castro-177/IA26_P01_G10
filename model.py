# model.py - modelacao do problema (Grupo 10)
#
# - cada linha de encomenda (order_item) e um pedido (Request)
# - cada pedido passa por 4 paragens: recolha no produtor -> descarga no armazem
#   -> carga no armazem -> entrega no cliente
# - uma paragem e um tuplo (tipo, local, pedidos), ex: ("recolha", 1, (31, 5))
# - uma solucao e um dicionario {id_veiculo: [paragens]}; os veiculos saem e voltam ao armazem
# - tempos em minutos desde 30/10 00:00; as janelas sao para o INICIO do servico (chegar cedo = esperar)
# - custo = km totais

from datetime import datetime

import pandas as pd

PASTA_TINY = "data/data_tiny_30_31oct2026"
PASTA_SMALL = "data/data_small_30_31oct2026"
INF = float("inf")


class Request:
    def __init__(self, id, peso, local_recolha, local_entrega, recolha, entrega):
        self.id = id
        self.peso = peso
        self.local_recolha = local_recolha  # location_id do produtor
        self.local_entrega = local_entrega  # location_id do cliente
        self.recolha = recolha              # janela (ini, fim) no produtor
        self.entrega = entrega              # janela (ini, fim) no cliente


class Vehicle:
    def __init__(self, id, capacidade, armazem):
        self.id = id
        self.capacidade = capacidade
        self.armazem = armazem  # location_id do centro de recolha


class State:
    # veiculos: tuplo com (local, tempo, carga, recolhidos, carregados) por veiculo
    # armazem: {pedido: (chegada, fim_descarga)}; rotas: paragens feitas (nao conta para comparar)
    def __init__(self, veiculos, por_recolher, armazem, entregues, rotas):
        self.veiculos = veiculos
        self.por_recolher = por_recolher
        self.armazem = armazem
        self.entregues = entregues
        self.rotas = rotas

    def chave(self):
        return (self.veiculos, self.por_recolher, tuple(sorted(self.armazem.items())))

    def __eq__(self, outro):
        return self.chave() == outro.chave()

    def __hash__(self):
        return hash(self.chave())

    def __lt__(self, outro):  # para o heapq nao falhar em empates
        return len(self.entregues) > len(outro.entregues)


class Problem:
    def __init__(self, pasta=PASTA_TINY, so_o_mais_atrasado=False):
        # so_o_mais_atrasado=True: em cada estado so mexe o veiculo com o tempo mais baixo
        # (muito menos estados na procura, mas pode perder a melhor solucao)
        self.so_o_mais_atrasado = so_o_mais_atrasado
        ler =lambda nome: pd.read_csv(f"{pasta}/{nome}.csv")
        regras = dict(zip(ler("rules")["rule"], ler("rules")["value"]))
        self.inicio = datetime.fromisoformat(regras["start_date"])
        self.horizonte = int(regras["horizon_days"]) * 1440
        self.servico = float(regras["stop_service_min"])                 # 10 min por recolha/entrega
        self.servico_armazem = float(regras["warehouse_handling_min"])   # 15 min descarga/carga
        self.max_armazem = float(regras["max_warehouse_dwell_h"]) * 60   # 24 h

        local = {(l.location_type, l.ref_id): l.location_id for l in ler("locations").itertuples()}
        self.dist = {(d.origin_location_id, d.destination_location_id): (d.distance_km, d.duration_min)
                     for d in ler("distance_matrix").itertuples()}
        self.veiculos = [Vehicle(v.vehicle_id, v.capacity_kg, local[("collection_center", v.center_id)])
                         for v in ler("vehicles").itertuples()]
        self.armazem = self.veiculos[0].armazem  # so ha um centro de recolha

        produtor = dict(zip(ler("products")["product_id"], ler("products")["producer_id"]))
        destino = dict(zip(ler("orders")["order_id"], ler("orders")["delivery_location_id"]))
        m = self.minutos
        self.pedidos = {}
        for i in ler("order_items").itertuples():
            self.pedidos[i.order_item_id] = Request(
                i.order_item_id, i.weight_kg,
                local[("producer", produtor[i.product_id])],
                local[("delivery_location", destino[i.order_id])],
                (m(i.availability_start), m(i.availability_end)),
                (m(i.delivery_start), m(i.delivery_end)))

    def minutos(self, data):
        return (datetime.fromisoformat(data) - self.inicio).total_seconds() / 60

    def km(self, a, b):
        return 0 if a == b else self.dist[(a, b)][0]

    def tempo(self, a, b):
        return 0 if a == b else self.dist[(a, b)][1]

    # atalhos para escrever rotas a mao
    def recolha(self, *ids): return ("recolha", self.pedidos[ids[0]].local_recolha, ids)
    def entrega(self, *ids): return ("entrega", self.pedidos[ids[0]].local_entrega, ids)
    def descarga(self, *ids): return ("descarga", self.armazem, ids)
    def carga(self, *ids): return ("carga", self.armazem, ids)

    # ------------------------------------------------------------ regras
    def janela(self, paragem, fim_descarga):
        tipo, _, ids = paragem
        if tipo in ("recolha", "entrega"):
            js = [getattr(self.pedidos[i], tipo) for i in ids]
            return max(j[0] for j in js), min(j[1] for j in js)
        if tipo == "carga":  # so depois de a descarga acabar (pode ter sido outro veiculo)
            return max(fim_descarga.get(i, 0) for i in ids), INF
        return 0, INF

    def avancar(self, local, t, paragem, fim_descarga):
        """Vai ate a paragem. Devolve (chegada, inicio, fim do servico, fim da janela)."""
        tipo, destino, _ = paragem
        chegada = t + self.tempo(local, destino)
        ini, fim = self.janela(paragem, fim_descarga)
        inicio = max(chegada, ini)
        servico = {"recolha": self.servico, "entrega": self.servico,
                   "descarga": self.servico_armazem, "carga": self.servico_armazem}.get(tipo, 0)
        return chegada, inicio, inicio + servico, fim

    # ------------------------------------------------------------ verificador
    def simular_rota(self, v, rota, fim_descarga):
        local, t, carga, a_bordo, km, erros, horarios = v.armazem, 0, 0, set(), 0, [], []
        for paragem in rota:
            tipo, sitio, ids = paragem
            if any(i not in self.pedidos for i in ids):
                erros.append(f"V{v.id} {paragem}: pedido que nao existe")
                continue
            # o local tem de bater certo com o tipo de paragem
            if tipo in ("recolha", "entrega"):
                certo = all(getattr(self.pedidos[i], "local_" + tipo) == sitio for i in ids)
            else:
                certo = sitio == v.armazem
            if not certo:
                erros.append(f"V{v.id} {paragem}: local errado")
            chegada, inicio, fim, fim_janela = self.avancar(local, t, paragem, fim_descarga)
            if inicio > fim_janela:
                erros.append(f"V{v.id} {paragem}: chega tarde demais")
            for i in ids:
                if tipo in ("recolha", "carga"):
                    a_bordo.add((tipo, i))
                    carga += self.pedidos[i].peso
                else:  # descarga tira o que foi recolhido, entrega tira o que foi carregado
                    antes = "recolha" if tipo == "descarga" else "carga"
                    if (antes, i) not in a_bordo:
                        erros.append(f"V{v.id} {paragem}: pedido {i} nao esta a bordo")
                    a_bordo.discard((antes, i))
                    carga -= self.pedidos[i].peso
            if carga > v.capacidade:
                erros.append(f"V{v.id} {paragem}: passa a capacidade ({carga:.1f} kg)")
            km += self.km(local, sitio)
            horarios.append((paragem, chegada, inicio, fim))
            local, t = sitio, fim
        km += self.km(local, v.armazem)
        if a_bordo:
            erros.append(f"V{v.id}: acaba com pedidos a bordo")
        if t + self.tempo(local, v.armazem) > self.horizonte:
            erros.append(f"V{v.id}: acaba depois do fim do horizonte")
        return km, erros, horarios

    def verificar(self, solucao, pedidos=None):
        """Devolve (valida, erros, km, horarios). 'pedidos' = os que tem de ser servidos (default todos)."""
        if pedidos is None:
            pedidos = self.pedidos
        # uma carga pode esperar pela descarga de outro veiculo: repetimos ate os tempos estabilizarem
        fim_descarga = {}
        for _ in range(10):
            res = {vid: self.simular_rota(self.veiculos[vid - 1], rota, fim_descarga)
                   for vid, rota in solucao.items()}
            novo = {i: fim for _, _, hs in res.values() for (tipo, _, ids), _, _, fim in hs
                    if tipo == "descarga" for i in ids}
            if novo == fim_descarga:
                break
            fim_descarga = novo

        erros = [e for _, es, _ in res.values() for e in es]
        visitas = {}  # (pedido, tipo) -> lista de (chegada, inicio, fim)
        for _, _, hs in res.values():
            for (tipo, _, ids), chegada, inicio, fim in hs:
                for i in ids:
                    visitas.setdefault((i, tipo), []).append((chegada, inicio, fim))
        for i in set(pedidos) | {i for i, _ in visitas}:
            for tipo in ("recolha", "descarga", "carga", "entrega"):
                n = len(visitas.get((i, tipo), []))
                if n != 1:
                    erros.append(f"pedido {i}: {n}x {tipo} (devia ser 1)")
            if len(visitas.get((i, "descarga"), [])) == 1 and len(visitas.get((i, "carga"), [])) == 1:
                chegada, _, fim_desc = visitas[(i, "descarga")][0]
                inicio_carga = visitas[(i, "carga")][0][1]
                if inicio_carga < fim_desc:
                    erros.append(f"pedido {i}: carregado antes de ser descarregado")
                if inicio_carga - chegada > self.max_armazem:
                    erros.append(f"pedido {i}: mais de 24 h no armazem")

        km = sum(k for k, _, _ in res.values())
        return len(erros) == 0, erros, km, {vid: hs for vid, (_, _, hs) in res.items()}

    def custo(self, solucao, penalizacao=1000):
        """km + penalizacao por cada erro (para a procura local comparar solucoes invalidas)."""
        _, erros, km, _ = self.verificar(solucao)
        return km + penalizacao * len(erros)

    # ------------------------------------------------------------ procura
    def estado_inicial(self):
        veiculos = tuple((v.armazem, 0, 0, frozenset(), frozenset()) for v in self.veiculos)
        return State(veiculos, frozenset(self.pedidos), {}, frozenset(), tuple(() for _ in self.veiculos))

    def objetivo(self, s):
        return len(s.entregues) == len(self.pedidos) and all(v[0] == self.armazem for v in s.veiculos)

    def a_tempo(self, i, t):
        """Se o pedido i sair do armazem em t, ainda chega a tempo ao cliente?"""
        r = self.pedidos[i]
        return t + self.servico_armazem + self.tempo(self.armazem, r.local_entrega) <= r.entrega[1]

    def acoes(self, s):
        """Acoes possiveis = lista de (indice_veiculo, paragem)."""
        # cortar se ha um pedido por recolher que ja nenhum veiculo consegue ir buscar
        for i in s.por_recolher:
            r = self.pedidos[i]
            if all(t + self.tempo(l, r.local_recolha) > r.recolha[1] for l, t, _, _, _ in s.veiculos):
                return []
        # ... ou um pedido a bordo / no armazem que ja nao chega a tempo ao cliente
        for l, t, _, recolhidos, carregados in s.veiculos:
            no_armazem = t + self.tempo(l, self.armazem)
            if any(not self.a_tempo(i, no_armazem + self.servico_armazem) for i in recolhidos):
                return []
            if any(t + self.tempo(l, self.pedidos[i].local_entrega) > self.pedidos[i].entrega[1] for i in carregados):
                return []
        for i, (chegou, fim_desc) in s.armazem.items():
            t_carga = min(max(t + self.tempo(l, self.armazem), fim_desc) for l, t, _, _, _ in s.veiculos)
            if t_carga - chegou > self.max_armazem or not self.a_tempo(i, t_carga):
                return []
        ordem = range(len(self.veiculos))
        if self.so_o_mais_atrasado:
            ordem = sorted(ordem, key=lambda k: s.veiculos[k][1])
        acoes = []
        for k in ordem:
            if self.so_o_mais_atrasado and acoes:
                break  # o veiculo mais atrasado ja tem acoes, os outros esperam
            v = self.veiculos[k]
            local, t, carga, recolhidos, carregados = s.veiculos[k]

            # ir a um produtor/cliente e recolher/entregar tudo o que der nesse momento
            for tipo, pedidos in (("recolha", s.por_recolher), ("entrega", carregados)):
                for sitio in {getattr(self.pedidos[i], "local_" + tipo) for i in pedidos}:
                    chegada = t + self.tempo(local, sitio)
                    abertos = [self.pedidos[i] for i in pedidos
                               if getattr(self.pedidos[i], "local_" + tipo) == sitio
                               and getattr(self.pedidos[i], tipo)[1] >= chegada]
                    if not abertos:
                        continue
                    inicio = max(chegada, min(getattr(r, tipo)[0] for r in abertos))
                    volta = inicio + self.servico + self.tempo(sitio, self.armazem) + self.servico_armazem
                    grupo, peso = [], carga
                    for r in sorted(abertos, key=lambda r: getattr(r, tipo)[1]):
                        ini, fim = getattr(r, tipo)
                        if not ini <= inicio <= fim:
                            continue
                        if tipo == "recolha" and (peso + r.peso > v.capacidade or not self.a_tempo(r.id, volta)):
                            continue
                        grupo.append(r.id)
                        peso += r.peso
                    if grupo:
                        acoes.append((k, (tipo, sitio, tuple(sorted(grupo)))))

            # descarregar tudo o que foi recolhido
            if recolhidos:
                acoes.append((k, ("descarga", self.armazem, tuple(sorted(recolhidos)))))

            # carregar os pedidos de um cliente que estao no armazem (os que couberem e derem a tempo)
            inicio = t + self.tempo(local, self.armazem)
            for cliente in {self.pedidos[i].local_entrega for i in s.armazem}:
                grupo, peso = [], carga
                for i in sorted(s.armazem, key=lambda i: self.pedidos[i].entrega[1]):
                    chegou, fim_desc = s.armazem[i]
                    t_carga = max(inicio, fim_desc)
                    if self.pedidos[i].local_entrega == cliente and peso + self.pedidos[i].peso <= v.capacidade \
                            and t_carga - chegou <= self.max_armazem and self.a_tempo(i, t_carga):
                        grupo.append(i)
                        peso += self.pedidos[i].peso
                if grupo:
                    acoes.append((k, ("carga", self.armazem, tuple(sorted(grupo)))))

            # voltar ao armazem se estiver vazio
            if local != self.armazem and not recolhidos and not carregados:
                acoes.append((k, ("regresso", self.armazem, ())))
        return acoes

    def resultado(self, s, acao):
        k, paragem = acao
        tipo, sitio, ids = paragem
        local, t, carga, recolhidos, carregados = s.veiculos[k]
        armazem, por_recolher, entregues = dict(s.armazem), s.por_recolher, s.entregues
        chegada, _, fim, _ = self.avancar(local, t, paragem, {i: f for i, (_, f) in armazem.items()})
        peso = sum(self.pedidos[i].peso for i in ids)
        ids = frozenset(ids)

        if tipo == "recolha":
            recolhidos, por_recolher, carga = recolhidos | ids, por_recolher - ids, carga + peso
        elif tipo == "descarga":
            recolhidos, carga = recolhidos - ids, carga - peso
            armazem.update({i: (chegada, fim) for i in ids})
        elif tipo == "carga":
            carregados, carga = carregados | ids, carga + peso
            for i in ids:
                del armazem[i]
        elif tipo == "entrega":
            carregados, entregues, carga = carregados - ids, entregues | ids, carga - peso

        veiculos, rotas = list(s.veiculos), list(s.rotas)
        veiculos[k] = (sitio, fim, carga, recolhidos, carregados)
        rotas[k] = rotas[k] + (paragem,)
        return State(tuple(veiculos), por_recolher, armazem, entregues, tuple(rotas))

    def custo_passo(self, s, acao):
        k, paragem = acao
        return self.km(s.veiculos[k][0], paragem[1])

    def solucao(self, s):
        return {v.id: list(rota) for v, rota in zip(self.veiculos, s.rotas)}
