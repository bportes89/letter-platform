# Checklist de staging

- [ ] DNS e TLS configurados.
- [ ] PostgreSQL gerenciado com backup e PITR.
- [ ] `LETTER_SECRET_KEY` forte no gerenciador de segredos.
- [ ] CORS limitado aos domínios oficiais.
- [ ] Bucket S3 privado, criptografado e com lifecycle.
- [ ] Migrações executadas antes da troca de tráfego.
- [ ] API e worker executados com usuários sem privilégio.
- [ ] Readiness e alertas monitorados.
- [ ] Backup restaurado em ensaio.
- [ ] Pentest e testes de carga aprovados.
- [ ] Fornecedores externos homologados.
- [ ] `LETTER_FINANCIAL_TRANSACTIONS_ENABLED=false` até aprovação formal.
