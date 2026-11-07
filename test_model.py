# Testes do model.py com rotas feitas a mao (dataset tiny). Correr: python -m unittest test_model -v
#
# Encomenda 10 (entrega na Casa 4 = location 8, 30/10 11:45-14:00):
#   pedido 30 - 3.8 kg no produtor 2 (location 2), 30/10 08:00-10:30
#   pedido 31 - 5.4 kg no produtor 1 (location 1), 30/10 07:15-09:45
# Armazem = location 4

import unittest

from model import Problem, Vehicle


class TestModelo(unittest.TestCase):

    def setUp(self):
        self.p = Problem()
        p = self.p
        self.rota = [p.recolha(31), p.recolha(30), p.descarga(30, 31), p.carga(30, 31), p.entrega(30, 31)]

    def erros(self, solucao, pedidos):
        return " | ".join(self.p.verificar(solucao, pedidos)[1])

    def test_leitura(self):
        self.assertEqual(len(self.p.pedidos), 40)
        self.assertEqual(self.p.pedidos[30].local_recolha, 2)
        self.assertEqual(self.p.pedidos[30].recolha, (8 * 60, 10.5 * 60))

    def test_rota_valida(self):
        p = self.p
        valida, erros, km, horarios = p.verificar({1: self.rota}, [30, 31])
        self.assertTrue(valida, erros)
        inicios = [h[2] for h in horarios[1]]
        self.assertEqual(inicios[0], 7 * 60 + 15)   # espera que o produtor 1 abra
        self.assertEqual(inicios[1], 8 * 60)        # chega 07:56 e espera ate as 08:00
        self.assertEqual(inicios[4], 11 * 60 + 45)  # espera que abra a janela de entrega
        self.assertAlmostEqual(km, p.km(4, 1) + p.km(1, 2) + p.km(2, 4) + p.km(4, 8) + p.km(8, 4))

    def test_dois_veiculos(self):
        # V1 recolhe e descarrega, V2 carrega e entrega (espera pela descarga do V1)
        p = self.p
        sol = {1: self.rota[:3], 2: self.rota[3:]}
        valida, erros, _, horarios = p.verificar(sol, [30, 31])
        self.assertTrue(valida, erros)
        self.assertEqual(horarios[2][0][2], horarios[1][-1][3])

    def test_capacidade(self):
        self.p.veiculos[0] = Vehicle(1, 5.0, 4)
        self.assertIn("capacidade", self.erros({1: self.rota}, [30, 31]))

    def test_recolha_tarde(self):
        p = self.p
        self.assertIn("tarde", self.erros({1: [p.recolha(30), p.recolha(29), p.recolha(31)]}, []))

    def test_entrega_tarde(self):
        p = self.p
        desvio = [p.recolha(1), p.descarga(1), p.carga(1), p.entrega(1)]   # pedido 1 e no dia 31
        self.assertIn("tarde", self.erros({1: self.rota[:4] + desvio + self.rota[4:]}, [1, 30, 31]))

    def test_entregar_sem_carregar(self):
        p = self.p
        self.assertIn("nao esta a bordo", self.erros({1: [p.recolha(30), p.entrega(30)]}, [30]))

    def test_falta_pedido(self):
        self.assertIn("pedido 1: 0x recolha", self.erros({1: self.rota}, None))

    def test_pedido_repetido(self):
        self.assertIn("2x recolha", self.erros({1: self.rota, 2: self.rota}, [30, 31]))

    def test_24h_no_armazem(self):
        p = self.p
        rota = [p.recolha(30), p.descarga(30), p.recolha(7), p.descarga(7), p.carga(30)]
        self.assertIn("24 h", self.erros({1: rota}, []))

    def test_local_errado(self):
        p = self.p
        rota = [("recolha", 1, (30,)), p.descarga(30), p.carga(30), ("entrega", 5, (30,))]
        self.assertIn("local errado", self.erros({1: rota}, [30]))

    def test_pedido_inexistente(self):
        self.assertIn("nao existe", self.erros({1: [("recolha", 1, (999,))]}, []))

    def test_carregar_antes_de_descarregar(self):
        # o mesmo veiculo carrega o 30 antes de o descarregar
        p = self.p
        rota = [p.recolha(30), p.carga(30), p.descarga(30), p.entrega(30)]
        self.assertIn("antes de ser descarregado", self.erros({1: rota}, [30]))

    def test_custo(self):
        p = self.p
        self.assertGreater(p.custo({1: [p.recolha(30), p.entrega(30)]}), 1000)

    def test_procura(self):
        # aplicar a rota com resultado() tem de dar o mesmo que o verificador
        p = self.p
        s = p.estado_inicial()
        self.assertTrue(p.acoes(s))
        km = 0
        for paragem in self.rota + [("regresso", 4, ())]:
            km += p.custo_passo(s, (0, paragem))
            s = p.resultado(s, (0, paragem))
        valida, erros, km_verif, _ = p.verificar(p.solucao(s), [30, 31])
        self.assertTrue(valida, erros)
        self.assertAlmostEqual(km, km_verif)
        self.assertEqual(s.entregues, {30, 31})


if __name__ == "__main__":
    unittest.main()
