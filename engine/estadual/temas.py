"""Os seis temas da triangulação estadual (escopo entregue a cada agente temático)."""

from ..perfil import P

_REDE = f"{P.estatal_ti.rede_governo}/{P.estatal_ti.sigla}" if P.estatal_ti.rede_governo else P.estatal_ti.sigla

TEMAS = {
    "1": {
        "nome": "Infraestrutura, nuvem e Data Center",
        "macros": ["Infraestrutura e nuvem"],
        "escopo": "Nuvem pública e privada, hospedagem, data center e colocation, servidores, storage e backup, "
                  "equipamentos e locação. Seções de candidatos: nuvem_e_hospedagem, produtos_repetidos, "
                  "fornecedores_multiorgao, mesmo_servico_mesmo_orgao, calendario. Pergunta central: o que deve "
                  f"convergir para {P.estatal()} e o futuro {P.datacenter_central.nome}, e onde há capacidade paralela.",
    },
    "2": {
        "nome": "Desenvolvimento e sustentação de sistemas",
        "macros": ["Desenvolvimento e sistemas"],
        "escopo": "Fábricas de software, sustentação, ordens de serviço por UST/PF/horas, sistemas finalísticos e "
                  "administrativos, BI, plataformas digitais e automação (inclusive plataformas de simplificação, "
                  "low-code, chatbot), IA. Seções: desenvolvimento, funcoes, produtos_repetidos, fornecedores_multiorgao. "
                  "Pergunta central: quanto o Estado paga por unidade de esforço em cada órgão, quantas fábricas "
                  "paralelas existem e quais sistemas/plataformas se repetem.",
    },
    "3": {
        "nome": "Licenciamento e plataformas",
        "macros": ["Licenciamento e plataformas"],
        "escopo": "Licenças de escritório e colaboração (Microsoft 365, Google Workspace), design e CAD/BIM (Adobe, "
                  "Autodesk, SketchUp, V-Ray, Lumion), segurança (antivírus, firewall, WAF), banco de dados e outras. "
                  "Inclua plataformas repetidas para a mesma função (BI, assinatura, simplificação) quando licenciadas. "
                  "Seções: produtos_repetidos, funcoes, atas, fora_de_ata_em_subcategoria_com_ata. Pergunta central: "
                  "a mesma licença comprada separadamente, a preços diferentes, e o que caberia em ata ou contrato corporativo.",
    },
    "4": {
        "nome": "Conectividade",
        "macros": ["Conectividade"],
        "escopo": f"Links de internet e rede de dados ({_REDE} e mercado), internet satelital (Starlink), telefonia "
                  "fixa e móvel, redes locais. Seções: produtos_repetidos, funcoes (Internet satelital), "
                  "fornecedores_multiorgao, atas, calendario. Pergunta central: contratos de acesso paralelos à rede "
                  "corporativa e compras isoladas de satélite e telefonia.",
    },
    "5": {
        "nome": "Serviços de TIC",
        "macros": ["Serviços de TIC"],
        "escopo": "Outsourcing de impressão, service desk e suporte, certificação digital e assinatura eletrônica, "
                  "consultoria e pesquisa (ex.: Gartner), digitalização e gestão documental, segurança gerenciada, "
                  "treinamento, suprimentos. Seções: produtos_repetidos, funcoes, atas, fora_de_ata_em_subcategoria_com_ata, "
                  "fornecedores_multiorgao. Pergunta central: serviços comuns contratados órgão a órgão e o que já tem ata.",
    },
    "6": {
        "nome": "Fornecedores, concentração e atas corporativas",
        "macros": [],
        "escopo": f"Visão transversal: fornecedores presentes em vários órgãos (inclusive {P.estatal()}), concentração de valor, "
                  f"atas {P.central('de')} e adesões, contratações fora de ata em subcategorias que já têm ata, mesmo fornecedor "
                  "com preços diferentes entre órgãos, contratos vencidos nos documentos. Seções: fornecedores_multiorgao, "
                  "atas, fora_de_ata_em_subcategoria_com_ata, calendario, panorama. Pergunta central: onde o poder de "
                  "compra do Estado está fragmentado.",
    },
}
