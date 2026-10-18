# Arquitecturas "completa el diagrama" en 4 nubes (Diseño de Sistemas Escalables, ITESO)

Verificado el 2026-10-16 contra documentación oficial: AWS con el AWS Knowledge MCP; Azure, GCP y OCI con WebFetch. Las
URL de GCP usan `docs.cloud.google.com`, porque `cloud.google.com` redirige ahí. Actualizado el 2026-10-17 para que
coincida con los puzzles corregidos de `arch-builder/puzzles/`: la columna de fuentes reúne, por slot, las URL que citan
los puzzles de las 4 nubes.

**Cómo leer la columna de distractores.** Va en el orden AWS / Azure / GCP / OCI y cierra con la razón por la que no
sirve. A veces el distractor es la respuesta de otro slot del mismo escenario. Es a propósito: esa es la confusión que
se evalúa.

**Requisitos por nube.** El requisito de la tabla es el común. Cuando una nube necesita otro texto para que su respuesta
sea única o esté respaldada, la variante va en la misma celda, marcada con el nombre de la nube.

**Tarjetas:** cada icono muestra el servicio **y su modalidad** cuando un mismo servicio puede cumplir papeles distintos
(instancia, grupo, réplica, standby).

**Reglas comunes:**

- **Zonas.** En AWS la subred vive en una AZ, pero en Azure y GCP es regional. Por eso las zonas se dibujan como
  columnas que cruzan las subredes, y así la topología sirve en las 4 nubes.
- **OCI en México.** Querétaro y Monterrey tienen un solo AD con 3 fault domains, así que en OCI la columna se rotula
  *fault domain* (<https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm>).
- **AWS en México.** mx-central-1 tiene 3 AZ (<https://aws.amazon.com/blogs/aws/now-open-aws-mexico-central-region/>).
- **Azure en México.** Mexico Central tiene 3 zonas
  (<https://learn.microsoft.com/en-us/azure/reliability/regions-list>).
- **GCP en México.** northamerica-south1 tiene 3 zonas repartidas en solo 1 o 2 centros de datos
  (<https://docs.cloud.google.com/compute/docs/regions-zones>).

---

## Escenario 1. Red privada con salida controlada (redes, NAT, gateways, grupos de seguridad y proxy de salida)

**Contexto:** 40 preparatorias de Jalisco publican calificaciones en un portal. La Secretaría exige que ni los
servidores ni la base de datos se puedan alcanzar desde internet.
**Topología:** una región con una VPC 10.0.0.0/16 y 2 zonas: una subred pública (balanceador) y dos privadas (app y BD).
Nodos fijos: alumnos, internet, laptop del administrador, servidores, BD, almacenamiento de objetos, SAT y banco.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Los servidores privados descargan parches de internet, pero nadie de afuera puede abrirles una conexión. | NAT gateway | Azure NAT Gateway | Cloud NAT | NAT Gateway | Internet gateway / IP pública en la VM / IP externa en la VM / Internet Gateway: dejan que internet inicie conexiones con el servidor o le dan una dirección pública. | <https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html> <https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html> <https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview> <https://docs.cloud.google.com/nat/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/NATgateway.htm> |
| 2 | Todo el tráfico web de salida pasa por un intermediario que solo deja llegar a los dominios del SAT, del banco y del repositorio de parches. GCP: es el proxy que cada servidor tiene configurado y, con inspección TLS, revisa la URL de cada petición HTTPS. | AWS Network Firewall (lista de dominios) | Azure Firewall (reglas FQDN) | Secure Web Proxy | OCI Network Firewall | Route 53 Resolver DNS Firewall (solo filtra la consulta DNS que pasa por el Resolver) / NSG (reglas por IP, CIDR, etiqueta de servicio o ASG) / Cloud NAT (solo traduce direcciones) y Cloud NGFW (intercepta sin estar configurado como proxy y solo lee el dominio) / security list (IP, protocolo y puerto): no son el intermediario que filtra por dominio o URL. | <https://docs.aws.amazon.com/network-firewall/latest/developerguide/stateful-rule-groups-domain-names.html> <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall-overview.html> <https://learn.microsoft.com/en-us/azure/firewall/features> <https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview> <https://docs.cloud.google.com/secure-web-proxy/docs/overview> <https://docs.cloud.google.com/nat/docs/overview> <https://docs.cloud.google.com/firewall/docs/about-url-filtering> <https://docs.oracle.com/en-us/iaas/Content/network-firewall/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm> |
| 3 | Solo los servidores de la app hablan con la BD por el 3306, estén en la subred que estén, y la respuesta regresa sola. Azure: el recurso se asocia a la subred de la BD y sus reglas solo dejan entrar por el 3306 a los servidores de la app. | security group | network security group | reglas de firewall de VPC (Cloud NGFW) | network security group | Network ACL (no guarda estado, va por subred) / application security group (solo agrupa interfaces; las reglas viven en el NSG) / Cloud Armor (resguarda backends de un balanceador) / security list (va por subred). | <https://docs.aws.amazon.com/vpc/latest/userguide/infrastructure-security.html> <https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview> <https://learn.microsoft.com/en-us/azure/virtual-network/application-security-groups> <https://docs.cloud.google.com/firewall/docs/firewalls> <https://docs.cloud.google.com/armor/docs/security-policy-overview> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm> |
| 4 | Los administradores abren una terminal en servidores sin IP pública, sin abrir el puerto 22 a internet, y cada sesión queda registrada. | AWS Systems Manager Session Manager | Azure Bastion | Identity-Aware Proxy (reenvío TCP) | OCI Bastion | Client VPN / VPN Gateway punto a sitio / Cloud VPN / Site-to-Site VPN: conectan un equipo o una red completa, no abren sesiones por servidor. | <https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html> <https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/what-is.html> <https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/connection-logging.html> <https://learn.microsoft.com/en-us/azure/bastion/bastion-overview> <https://learn.microsoft.com/en-us/azure/vpn-gateway/point-to-site-about> <https://docs.cloud.google.com/iap/docs/using-tcp-forwarding> <https://docs.cloud.google.com/network-connectivity/docs/vpn/concepts/overview> <https://docs.oracle.com/en-us/iaas/Content/Bastion/Concepts/bastionoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingIPsec.htm> |
| 5 | Las boletas PDF llegan al almacenamiento de objetos sin salir a internet ni pasar por el slot 1. GCP: los servidores, que solo tienen IP interna, las llevan sin pasar por el slot 1. | gateway VPC endpoint (S3) | private endpoint (Private Link) | Private Google Access | Service Gateway | VPC peering / VNet peering / VPC Network Peering / Local Peering Gateway: unen redes, no dan acceso a un servicio. | <https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html> <https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html> <https://learn.microsoft.com/en-us/azure/storage/common/storage-private-endpoints> <https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview> <https://docs.cloud.google.com/vpc/docs/private-google-access> <https://docs.cloud.google.com/nat/docs/overview> <https://docs.cloud.google.com/vpc/docs/vpc-peering> <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/servicegateway.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/localVCNpeering.htm> |
| 6 | Guarda el origen, el destino y el puerto del tráfico de red de los servidores para investigar un escaneo. | VPC Flow Logs | virtual network flow logs | VPC Flow Logs | VCN flow logs | CloudTrail / registro de actividad / Cloud Audit Logs / Audit: registran llamadas a la API u operaciones de administración, no tráfico. | <https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html> <https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html> <https://learn.microsoft.com/en-us/azure/network-watcher/vnet-flow-logs-overview> <https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/activity-log> <https://docs.cloud.google.com/vpc/docs/flow-logs> <https://docs.cloud.google.com/iap/docs/using-tcp-forwarding> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/vcn-flow-logs.htm> <https://docs.oracle.com/en-us/iaas/Content/Bastion/Concepts/bastionoverview.htm> |

**Equivalencias:**

- **Azure** no tiene recurso de internet gateway. Las VNet nuevas, con API posterior al 31-mar-2026, traen subredes
  privadas por defecto. Los NSG flow logs se retiran el 30-sep-2027.
- **Azure (slot 3):** el requisito común ("estén en la subred que estén") apunta al application security group, que
  agrupa VM sin importar la subred. Por eso en Azure el requisito pide el recurso que se asocia a la subred de la BD y
  contiene las reglas; el ASG queda como distractor
  (<https://learn.microsoft.com/en-us/azure/virtual-network/application-security-groups>).
- **GCP (slot 2):** Cloud NGFW también filtra por dominio (FQDN y filtrado de URL, que lee el SNI o el encabezado host).
  Elegimos Secure Web Proxy porque el requisito de GCP pide un proxy explícito que revise la URL completa
  (<https://docs.cloud.google.com/firewall/docs/about-url-filtering>).
- **GCP (slot 5):** la documentación de Private Google Access no dice que el tráfico no salga a internet, así que el
  requisito de GCP solo pide que los servidores con IP interna lleguen al almacenamiento sin pasar por el slot 1
  (<https://docs.cloud.google.com/vpc/docs/private-google-access>).
- **OCI:** el Local Peering Gateway es heredado; hoy se recomienda DRG.

---

## Escenario 2. Tienda que aguanta el Buen Fin (cómputo, autoescalado, balanceo L7, terminación TLS y monitoreo)

**Contexto:** una cooperativa de artesanos de Tlaquepaque multiplica por diez su tráfico en el Buen Fin. Debe crecer
sola y no perder ventas si cae una zona (en OCI, un dominio de falla).
**Topología:** una región con una VPC y 2 zonas: una subred pública (balanceador) y una privada (servidores). Nodos
fijos: compradores, internet, BD administrada y equipo de guardia.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Es cada servidor individual: tiene su propio sistema operativo que el equipo parcha, su agente de inventario instalado y atiende todo el día. | Amazon EC2 | Azure Virtual Machines | Compute Engine | OCI Compute (VM) | Lambda (corta a los 15 min) / Azure Functions (sin servidores, por evento) / Cloud Run functions (por evento o solicitud) / OCI Functions (corta a los 300 s): no son un servidor propio que el equipo parcha. | <https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html> <https://learn.microsoft.com/en-us/azure/virtual-machines/overview> <https://learn.microsoft.com/en-us/azure/azure-functions/functions-overview> <https://docs.cloud.google.com/compute/docs/overview> <https://docs.cloud.google.com/run/docs/functions/comparison> <https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionscustomizing.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/computeoverview.htm> |
| 2 | Mantiene de 2 a 20 copias en ambas zonas, agrega o quita según la carga y reemplaza las que fallan. OCI: en ambos dominios de falla, y repone las que se terminan. | EC2 Auto Scaling (grupo) | Virtual Machine Scale Sets | grupo de instancias administrado (MIG) | instance pool con autoscaling | Launch template / availability set / grupo no administrado / instance configuration: son plantillas o reparto, no escalan. | <https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-health-checks.html> <https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-autoscale-overview> <https://learn.microsoft.com/en-us/azure/virtual-machines/availability-set-overview> <https://docs.cloud.google.com/compute/docs/autoscaler> <https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/autoscalinginstancepools.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instance-pools.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/autoscaling-create-metric-based_tabs.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instancemanagement.htm> |
| 3 | Recibe y descifra el HTTPS, manda `/api` a un grupo y `/tienda` a otro, y solo envía a servidores sanos. | Application Load Balancer | Application Gateway v2 | balanceador de aplicaciones externo regional | OCI Load Balancer (flexible) | Network Load Balancer / Azure Load Balancer / balanceador de red de paso externo / Network Load Balancer: son capa 4 y no leen la URL. | <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://learn.microsoft.com/en-us/azure/application-gateway/overview> <https://docs.cloud.google.com/load-balancing/docs/https> <https://docs.cloud.google.com/load-balancing/docs/network/networklb-backend-service> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingcertificates.htm> <https://docs.oracle.com/en-us/iaas/Content/NetworkLoadBalancer/overview.htm> |
| 4 | Es lo que el slot 3 presenta al navegador para probar que es `tienda.mx`. AWS y GCP: lo emite y lo renueva automáticamente. Azure: lo obtiene de una autoridad emisora asociada y lo renueva automáticamente. OCI: lo guarda (lo emite una autoridad externa y aquí se importa) y administra sus versiones. | AWS Certificate Manager | Azure Key Vault (certificados) | Certificate Manager | OCI Certificates (importa el certificado que emitió una CA externa) | AWS KMS / Key Vault Managed HSM (no admite certificados) / Cloud KMS / llave de OCI Vault (también tiene versiones): guardan llaves, no certificados. | <https://docs.aws.amazon.com/acm/latest/userguide/dns-renewal-validation.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/https-listener-certificates.html> <https://docs.aws.amazon.com/kms/latest/developerguide/overview.html> <https://learn.microsoft.com/en-us/azure/application-gateway/key-vault-certs> <https://learn.microsoft.com/en-us/azure/key-vault/general/about-keys-secrets-certificates> <https://learn.microsoft.com/en-us/azure/key-vault/certificates/about-certificates> <https://docs.cloud.google.com/certificate-manager/docs/overview> <https://docs.cloud.google.com/kms/docs/key-management-service> <https://docs.oracle.com/en-us/iaas/Content/certificates/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Concepts/keyoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingcertificates.htm> |
| 5 | Registra la CPU cada minuto y avisa a guardia si pasa de 80 % durante 5 minutos. | Amazon CloudWatch (alarmas) | Azure Monitor (alertas de métricas) | Cloud Monitoring (alertas) | OCI Monitoring (alarmas) | Trusted Advisor / Azure Advisor / Recommender / Cloud Advisor: dan recomendaciones periódicas, no alertas. | <https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-scaling-simple-step.html> <https://aws.amazon.com/premiumsupport/technology/trusted-advisor/> <https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-types> <https://learn.microsoft.com/en-us/azure/advisor/advisor-overview> <https://docs.cloud.google.com/monitoring/alerts> <https://docs.cloud.google.com/recommender/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/CloudAdvisor/Concepts/cloudadvisoroverview.htm> |

**Equivalencias:**

- **Slot 1:** el requisito dice "cada servidor individual" para que no lo cumpla el grupo del slot 2 (Auto Scaling,
  scale set, MIG o instance pool).
- **Slot 4:** el requisito no dice "certificado", porque la palabra delataba la respuesta. Describe la función y cada
  nube dice cómo lo obtiene.
- **Azure:** Application Gateway v1 se retiró el 28-abr-2026, y Key Vault solo funciona con v2. Key Vault no emite el
  certificado: lo pide a una CA asociada (DigiCert o GlobalSign) y lo renueva
  (<https://learn.microsoft.com/en-us/azure/key-vault/certificates/about-certificates>).
- **OCI (slot 2):** el instance pool reparte instancias entre dominios de falla y crea otra cuando se termina una
  (<https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instance-pools.htm>). Por eso el requisito de OCI dice
  "repone las que se terminan" y no "reemplaza las que fallan".
- **OCI:** los *path route sets* se van a retirar; se usarán *routing policies*.

---

## Escenario 3. Cursos en video (CDN, caché, clases de almacenamiento, DNS público y WAF)

**Contexto:** CursosMX vende cursos grabados a 300 mil alumnos de México y Centroamérica. Los videos deben llegar
rápido, las grabaciones crudas deben costar poco y el login recibe intentos de inyección SQL.
**Topología:** usuarios → entrada (slot 1) → videos (slot 2) y un balanceador fijo con login y pagos. El slot 5 es una
política asociada a ese balanceador, no un paso de red. El slot 4 está fuera de la región. El cuadro de entrada se
rotula "Entrada desde internet" (en OCI, "Entrada en Querétaro"). En OCI el slot 1 es la caché a la entrada del
balanceador y los videos salen directo de Object Storage (ver Equivalencias).

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Guarda copias de videos e imágenes en puntos cercanos a cada alumno, para no viajar hasta la región en cada petición. OCI: contesta desde la región las páginas e imágenes que más se piden, sin que la petición llegue a los servidores, y no guarda archivos de más de 100 MB. | Amazon CloudFront | Azure Front Door (Standard/Premium) | Cloud CDN | **Sin equivalente:** Web Application Acceleration (caché del balanceador) | Global Accelerator (reenvía paquetes TCP y UDP) / Traffic Manager (solo DNS) / bucket birregional (replica en dos regiones) / OCI Cache (memoria para aplicaciones, solo por endpoint privado): ninguno guarda copias cerca del alumno. | <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html> <https://aws.amazon.com/global-accelerator/faqs/> <https://learn.microsoft.com/en-us/azure/frontdoor/front-door-overview> <https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-how-it-works> <https://docs.cloud.google.com/cdn/docs/overview> <https://docs.cloud.google.com/storage/docs/locations> <https://docs.oracle.com/en-us/iaas/Content/web-app-acceleration/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/ocicache/home.htm> |
| 2 | Origen de millones de videos que los alumnos ven a diario por HTTP; se paga por GB guardado y no hay servidores que administrar. AWS y Azure: en una sola región. GCP: los datos se quedan en una sola región de México. OCI: los entrega directo por internet. | Amazon S3 | Azure Blob Storage (nivel Hot) | Cloud Storage | OCI Object Storage | EBS / discos administrados / Persistent Disk / Block Volume: son discos de una VM. También S3 Standard-IA / nivel Cool / Nearline / Infrequent Access: cobran cada GB que se lee. GCP: bucket birregional (guarda en un par de regiones y Querétaro no está en ningún par). OCI: OCI Cache. | <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html> <https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html> <https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html> <https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-overview> <https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview> <https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview> <https://docs.cloud.google.com/storage/docs/introduction> <https://docs.cloud.google.com/storage/docs/locations> <https://docs.cloud.google.com/storage/docs/storage-classes> <https://docs.cloud.google.com/cdn/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/understandingstoragetiers.htm> <https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/ocicache/home.htm> |
| 3 | Las grabaciones crudas se guardan 5 años y casi nunca se abren. Importa el menor costo por GB guardado, aunque leerlas después sea más caro o más lento. Azure: el menor costo por GB guardado que ofrece la región, aunque leerlas después sea más caro. | S3 Glacier Deep Archive | Blob, nivel Cold | Cloud Storage, clase Archive | Object Storage, nivel Archive | S3 Standard-IA / nivel Cool / Nearline / Infrequent Access: no son la clase más barata por GB (en Azure, de las que ofrece Mexico Central). | <https://docs.aws.amazon.com/whitepapers/latest/oracle-database-aws-best-practices/backup-storage.html> <https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html> <https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview> <https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview> <https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table> <https://docs.cloud.google.com/storage/docs/storage-classes> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/understandingstoragetiers.htm> <https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/overview.htm> |
| 4 | Guarda los registros de `cursosmx.com` y responde a cualquiera en internet que pregunte por ese nombre, para que llegue al slot 1 (OCI: a la entrada en Querétaro). | Route 53 (zona pública) | Azure DNS (zona pública) | Cloud DNS (zona pública) | OCI DNS (zona pública) | Zona privada / Azure Private DNS / zona privada / zona privada: solo responden dentro de la red. Azure: también Traffic Manager, que solo elige un endpoint. | <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-routing-traffic-to-resources.html> <https://learn.microsoft.com/en-us/azure/dns/dns-overview> <https://docs.cloud.google.com/dns/docs/zones/zones-overview> <https://docs.oracle.com/en-us/iaas/Content/DNS/Tasks/privatedns.htm> |
| 5 | Revisa cada petición HTTP del login y bloquea la inyección SQL antes de que llegue a la app. | AWS WAF (web ACL asociada al balanceador) | Azure Web Application Firewall en Application Gateway (WAF_v2) | Google Cloud Armor (reglas WAF en el backend service) | OCI Web Application Firewall (política del balanceador) | Shield Standard / DDoS Protection / reglas de firewall de VPC / NSG: protegen las capas 3 y 4 o filtran por IP y puerto, no buscan inyección SQL. | <https://docs.aws.amazon.com/waf/latest/developerguide/what-is-aws-waf.html> <https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/ag-overview> <https://learn.microsoft.com/en-us/azure/ddos-protection/ddos-protection-overview> <https://docs.cloud.google.com/armor/docs/waf-rules> <https://docs.cloud.google.com/armor/docs/security-policy-overview> <https://docs.cloud.google.com/firewall/docs/firewalls> <https://docs.oracle.com/en-us/iaas/Content/WAF/Concepts/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm> |

**Equivalencias:**

- **OCI (slot 1):** no aparece ninguna CDN en su índice de servicios. Es una inferencia: la documentación no dice "no
  existe". Web Application Acceleration es una política de un balanceador HTTP que guarda en caché respuestas de sus
  servidores backend, hasta 100 MB por archivo, y la página no menciona Object Storage
  (<https://docs.oracle.com/en-us/iaas/Content/web-app-acceleration/overview.htm>). Por eso en OCI el slot 1 guarda
  páginas e imágenes de los servidores, el nodo fijo se rotula "Backend set del balanceador" y la flecha del slot 1 al
  slot 2 es punteada, sin paso ("videos: directo, no por la caché"), porque Web Application Acceleration solo se asocia
  a un balanceador.
- **Azure (slot 3):** la tabla de productos por región lista en Mexico Central los niveles Hot, Cool y Cold de Blob
  Storage y no Archive Storage
  (<https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table>). Se conserva la región:
  la respuesta es el nivel Cold, con 90 días mínimos y menor costo de almacenamiento que Cool
  (<https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview>). Por eso el requisito de Azure pide el
  menor costo que ofrece la región, Archive salió de la paleta y Cool sigue como near-miss.
- **Azure (slot 5):** el WAF de Front Door corre dentro del slot 1, y la geometría común asocia la política al
  balanceador en las 4 nubes. Por eso la respuesta es el WAF de Application Gateway, cuya política se asocia al
  Application Gateway que hace de balanceador fijo
  (<https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/ag-overview>). Azure CDN (classic) se retira el
  30-sep-2027.
- **GCP (slot 2):** el requisito pide que los datos se queden en una sola región de México y no habla de precio. La
  respuesta es un bucket regional en northamerica-south1, clase Standard, la de datos que se leen seguido
  (<https://docs.cloud.google.com/storage/docs/locations>,
  <https://docs.cloud.google.com/storage/docs/storage-classes>).
- **GCP (slot 5):** Cloud Armor se adjunta al backend service del balanceador; a los backend buckets solo se les aplican
  políticas de borde, así que el slot 5 resguarda solo la parte dinámica
  (<https://docs.cloud.google.com/armor/docs/security-policy-overview>).
- **GCP (balanceador fijo):** Cloud CDN solo funciona con el balanceador de aplicaciones externo global o el clásico,
  así que el nodo fijo es el global. Se dibuja dentro de la región y la VPC para conservar la geometría; es una
  simplificación (<https://docs.cloud.google.com/cdn/docs/overview>).

---

## Escenario 4. Estudio de animación

**Temas:** archivos compartidos NFS frente a objetos, sistema paralelo, redundancia, cómputo interrumpible y VPN.
**Contexto:** un estudio tapatío renderiza un cortometraje de noche en 200 VM que leen las mismas escenas. Los artistas
trabajan desde su oficina y ninguna escena se puede perder.
**Topología:** oficina (fija) ↔ slot 5 ↔ VPC en México con 2 zonas y una subred privada, donde están la granja (slot 4)
y el almacenamiento (slots 1 a 3).

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Cientos de servidores Linux montan a la vez la carpeta de proyectos por NFS, disponible en ambas zonas (OCI: en ambos dominios de falla). Azure: además, los artistas la editan en su lugar. | Amazon EFS (regional) | Azure Files (SSD) | Filestore (regional) | OCI File Storage | EBS (Multi-Attach solo io1/io2, 16 instancias de una zona) / discos administrados / Persistent Disk (escritura múltiple con máximo 2 VM de una zona) / Block Volume: son bloques, no carpetas compartidas. Azure: también Blob Storage con NFS 3.0, que Microsoft desaconseja para editar en su lugar. GCP: también Filestore zonal (una sola zona). | <https://docs.aws.amazon.com/efs/latest/ug/how-it-works.html> <https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html> <https://learn.microsoft.com/en-us/azure/storage/files/files-nfs-protocol> <https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy> <https://learn.microsoft.com/en-us/azure/storage/blobs/network-file-system-protocol-support> <https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview> <https://docs.cloud.google.com/filestore/docs/overview> <https://docs.cloud.google.com/compute/docs/disks/sharing-disks-between-vms> <https://docs.cloud.google.com/filestore/docs/regions> <https://docs.oracle.com/en-us/iaas/Content/File/Concepts/filestorageoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/overview.htm> |
| 2 | Conserva la versión de anoche de la carpeta de proyectos, para recuperar una escena que alguien borre por error. | AWS Backup | instantáneas de Azure Files | respaldos de Filestore | instantáneas de OCI File Storage | Replicación de EFS / Azure Backup (no admite recursos compartidos NFS) / replicación de instancias de Filestore / replicación de File Storage: las réplicas mantienen la copia al día y no guardan la versión de anoche. | <https://docs.aws.amazon.com/efs/latest/ug/awsbackup.html> <https://docs.aws.amazon.com/efs/latest/ug/efs-replication.html> <https://learn.microsoft.com/en-us/azure/storage/files/storage-snapshots-files> <https://learn.microsoft.com/en-us/azure/storage/files/files-nfs-protocol> <https://learn.microsoft.com/en-us/azure/backup/azure-file-share-support-matrix> <https://docs.cloud.google.com/filestore/docs/backup-restore> <https://docs.cloud.google.com/filestore/docs/overview> <https://docs.cloud.google.com/filestore/docs/instance-replication> <https://docs.oracle.com/iaas/Content/File/Tasks/managingsnapshots.htm> <https://docs.oracle.com/en-us/iaas/Content/File/Concepts/filestorageoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/File/Tasks/FSreplication.htm> |
| 3 | Los cuadros terminados se guardan años, se leen por HTTP y sobreviven a la pérdida de una zona completa. OCI: se leen por HTTP desde internet y no dependen de ninguna instancia. | S3 Standard | Blob Storage con ZRS | Cloud Storage regional | OCI Object Storage | S3 One Zone-IA (una AZ) / Blob LRS (un centro de datos) / Filestore zonal (una zona) / Block Volume (disco de VM). | <https://docs.aws.amazon.com/AmazonS3/latest/userguide/DataDurability.html> <https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy> <https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview> <https://docs.cloud.google.com/storage/docs/availability-durability> <https://docs.cloud.google.com/filestore/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/overview.htm> |
| 4 | Los nodos de render pueden apagarse con segundos o minutos de aviso porque el trabajo se reanuda. Importa el precio más bajo, sin compromiso. | Spot Instances de EC2 | Azure Spot Virtual Machines | Spot VMs | instancias preemptible | Savings Plans / Reservations / descuentos por compromiso: exigen 1 o 3 años. Reserva de capacidad de OCI: aparta capacidad que se cobra a la tarifa normal, no abarata. | <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html> <https://repost.aws/knowledge-center/ec2-spot-instance-unexpected-termination> <https://docs.aws.amazon.com/savingsplans/latest/APIReference/Welcome.html> <https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms> <https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/save-compute-costs-reservations> <https://docs.cloud.google.com/compute/docs/instances/spot> <https://docs.cloud.google.com/compute/docs/instances/committed-use-discounts-overview> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/preemptible.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/reserve-capacity.htm> |
| 5 | La oficina se une hoy mismo a la red de la nube, cifrada, por el internet que ya tiene. | AWS Site-to-Site VPN | VPN Gateway (sitio a sitio) | Cloud VPN (HA VPN) | OCI Site-to-Site VPN | Direct Connect / ExpressRoute / Cloud Interconnect / FastConnect: son conexiones dedicadas o privadas que no usan el internet de la oficina. | <https://docs.aws.amazon.com/vpn/latest/s2svpn/data-protection.html> <https://docs.aws.amazon.com/vpn/latest/s2svpn/VPC_VPN.html> <https://docs.aws.amazon.com/whitepapers/latest/hybrid-connectivity/hybrid-network-connections.html> <https://docs.aws.amazon.com/directconnect/latest/APIReference/Welcome.html> <https://learn.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-about-vpngateways> <https://learn.microsoft.com/en-us/azure/expressroute/expressroute-introduction> <https://docs.cloud.google.com/network-connectivity/docs/vpn/concepts/overview> <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/overviewIPsec.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/fastconnect.htm> |

**Equivalencias:**

- **Erasure coding:** Google lo documenta en Cloud Storage y OCI en File Storage ("Data is protected with erasure
  encoding", <https://docs.oracle.com/en-us/iaas/Content/File/Concepts/filestorageoverview.htm>). Como no todas las
  nubes lo documentan, el requisito del slot 3 pide sobrevivir a la pérdida de una zona y no nombra la técnica.
- **OCI:** no documenta su redundancia por zona y tiene un solo AD en Querétaro. Su requisito 3 pide, en cambio, que los
  cuadros se lean desde internet sin depender de ninguna instancia
  (<https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm>).
- **Azure (slot 1):** Blob Storage con ZRS también se monta por NFS 3.0, pero Microsoft lo desaconseja para recursos
  compartidos de uso general y para editar archivos en su lugar, y recomienda Azure Files. Por eso solo el requisito de
  Azure agrega "que los artistas editan en su lugar"
  (<https://learn.microsoft.com/en-us/azure/storage/blobs/network-file-system-protocol-support>).
- **Azure (slot 2):** la ficha ZRS ("del recurso compartido") salió de la paleta porque competía con Azure Files en el
  slot 1. El near-miss es Azure Backup, que según su matriz de soporte no admite recursos compartidos NFS
  (<https://learn.microsoft.com/en-us/azure/backup/azure-file-share-support-matrix>).
- **GCP (slot 1):** la página de regiones de Filestore lista northamerica-south1, con las zonas a, b y c, sin
  restricción por nivel, y la del nivel regional no menciona límites de región
  (<https://docs.cloud.google.com/filestore/docs/regions>,
  <https://docs.cloud.google.com/filestore/docs/service-tiers-regional>).
- **Respaldo frente a réplica:** la réplica sirve contra la pérdida de una zona, no contra un borrado, porque mantiene
  la copia al día y no guarda la versión de anoche. Esa es la confusión que evalúa el slot 2. Cada nube cita su página:
  EFS mantiene la copia sincronizada (<https://docs.aws.amazon.com/efs/latest/ug/efs-replication.html>), la réplica de
  Filestore se actualiza de forma continua y no se puede montar
  (<https://docs.cloud.google.com/filestore/docs/instance-replication>) y la replicación de File Storage borra la
  instantánea anterior en cada intervalo (<https://docs.oracle.com/en-us/iaas/Content/File/Tasks/FSreplication.htm>).
- **Aviso antes de interrumpir:** AWS y OCI dan 2 min, Azure 30 s y GCP de 0 a 120 s.

---

## Escenario 5. Pagos de becas

**Temas (seguridad):** OAuth 2.0 con proveedor de identidad tipo Keycloak, tokens, llaves, amenazas y auditoría.
**Contexto:** BecaPay deposita apoyos a 15 mil universitarios por una app. El auditor exige un login estándar, llaves
propias y un rastro de cada cambio.
**Topología:** app → slot 1 → slot 2 → VPC con 2 zonas y subred privada (pagos y BD fijos). Los slots 3 a 5 son
servicios regionales junto a la VPC.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Los alumnos entran con correo o con su cuenta de Google, y la app recibe tokens OAuth 2.0 / OIDC que caducan y se renuevan con un token de actualización. | Amazon Cognito (grupos de usuarios) | Microsoft Entra External ID | Identity Platform | OCI IAM con dominios de identidad | IAM / Azure RBAC / IAM / políticas de IAM: controlan quién administra los recursos de la nube, no el login de los clientes de la app. | <https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html> <https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-id-token.html> <https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-refresh-token.html> <https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html> <https://aws.amazon.com/compare/cognito-and-iam/> <https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam> <https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens> <https://learn.microsoft.com/en-us/entra/external-id/customers/concept-supported-features-customers> <https://learn.microsoft.com/en-us/azure/role-based-access-control/overview> <https://docs.cloud.google.com/identity-platform/docs/concepts> <https://docs.cloud.google.com/identity-platform/docs/use-rest-api> <https://docs.cloud.google.com/iam/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Identity/identityproviders/add-social-identity-provider.htm> <https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm> <https://docs.oracle.com/en-us/iaas/Content/Identity/policieshow/how-policies-work.htm> |
| 2 | Cualquier llamada a `/pagos` con un token inválido, caducado o de otro emisor se rechaza antes de llegar al servicio. GCP: además, la pieza corre en la región de México. | Amazon API Gateway | Azure API Management | Apigee | OCI API Gateway | NLB / Azure Load Balancer / balanceador de red de paso / Network Load Balancer: son capa 4 y no leen tokens. GCP: también API Gateway, que valida JWT pero no se despliega en ninguna región de México. | <https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html> <https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html> <https://learn.microsoft.com/en-us/azure/api-management/validate-jwt-policy> <https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview> <https://docs.cloud.google.com/api-gateway/docs/authenticating-users-jwt> <https://docs.cloud.google.com/load-balancing/docs/passthrough-network-load-balancer> <https://docs.cloud.google.com/apigee/docs/api-platform/reference/policies/verify-jwt-policy> <https://docs.cloud.google.com/apigee/docs/locations> <https://docs.cloud.google.com/api-gateway/docs/deployment-model> <https://docs.oracle.com/en-us/iaas/Content/APIGateway/Tasks/apigatewayusingjwttokens.htm> <https://docs.oracle.com/en-us/iaas/Content/NetworkLoadBalancer/overview.htm> |
| 3 | La BD y los respaldos se cifran con llaves de la empresa que rotan cada año, y cada uso de esas llaves se puede registrar. | AWS KMS | Azure Key Vault (llaves) | Cloud KMS | OCI Vault (llaves) | Secrets Manager / App Configuration / Secret Manager / Secret Management: guardan secretos o configuración, no crean ni rotan las llaves de cifrado. | <https://docs.aws.amazon.com/help-panel/kms/latest/console/hp-automatic-key-rotation.html> <https://docs.aws.amazon.com/kms/latest/developerguide/logging-using-cloudtrail.html> <https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html> <https://docs.aws.amazon.com/secretsmanager/latest/userguide/security-encryption.html> <https://learn.microsoft.com/en-us/azure/key-vault/keys/how-to-configure-key-rotation> <https://learn.microsoft.com/en-us/azure/key-vault/general/logging> <https://learn.microsoft.com/en-us/azure/azure-app-configuration/overview> <https://docs.cloud.google.com/kms/docs/key-rotation> <https://docs.cloud.google.com/kms/docs/audit-logging> <https://docs.cloud.google.com/logging/docs/audit> <https://docs.cloud.google.com/secret-manager/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Concepts/keyoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Logging/Reference/details_for_kms.htm> <https://docs.oracle.com/en-us/iaas/Content/secret-management/home.htm> |
| 4 | Alerta si alguien opera los recursos de la nube desde una IP sospechosa. | Amazon GuardDuty | Microsoft Defender for Cloud | Security Command Center (nivel Premium) | Oracle Cloud Guard | Inspector / Azure Policy / Artifact Analysis / Vulnerability Scanning: buscan vulnerabilidades o revisan cumplimiento, no actividad. | <https://aws.amazon.com/guardduty/pricing/> <https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_finding-types-iam.html> <https://docs.aws.amazon.com/inspector/latest/user/what-is-inspector.html> <https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-cloud-introduction> <https://learn.microsoft.com/en-us/azure/defender-for-cloud/alerts-resource-manager> <https://learn.microsoft.com/en-us/azure/governance/policy/overview> <https://docs.cloud.google.com/security-command-center/docs/concepts-event-threat-detection-overview> <https://docs.cloud.google.com/artifact-analysis/docs/container-scanning-overview> <https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm> <https://docs.oracle.com/en-us/iaas/cloud-guard/using/detect-recipes.htm> <https://docs.oracle.com/en-us/iaas/scanning/home.htm> |
| 5 | El auditor ve quién cambió una regla de firewall o borró un recurso, cuándo y desde dónde. | AWS CloudTrail | registro de actividad de Azure Monitor | Cloud Audit Logs | OCI Audit | Registros de flujo de VPC / VNet / VPC / VCN: registran tráfico, no acciones. | <https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudtrail.html> <https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html> <https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html> <https://learn.microsoft.com/en-us/azure/azure-monitor/platform/activity-log> <https://learn.microsoft.com/en-us/azure/network-watcher/vnet-flow-logs-overview> <https://docs.cloud.google.com/logging/docs/audit> <https://docs.cloud.google.com/logging/docs/reference/audit/auditlog/rest/Shared.Types/AuditLog> <https://docs.cloud.google.com/vpc/docs/flow-logs> <https://docs.oracle.com/en-us/iaas/Content/Audit/Concepts/auditoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Audit/Reference/logeventreference.htm> <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/vcn-flow-logs.htm> |

**Equivalencias:**

- **Slot 1:** no hay una duración de token que las 4 nubes respalden: Cognito acepta de 5 minutos a 1 día y el token de
  ID de Identity Platform no tiene duración configurable. Las 4 sí documentan el token de actualización, y eso pide el
  requisito
  (<https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-id-token.html>,
  <https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens>,
  <https://docs.cloud.google.com/identity-platform/docs/use-rest-api>,
  <https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm>).
- **Slot 2:** las tarjetas no llevan modo; la explicación nombra el autorizador JWT de API Gateway, la política
  validate-jwt de API Management y la política VerifyJWT de Apigee.
- **AWS (slot 2):** API Gateway llega a la subred privada con una integración privada por VPC link, hacia un ALB, un NLB
  o Cloud Map
  (<https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html>).
- **GCP (slot 2):** API Gateway solo se despliega en 10 regiones y ninguna está en México
  (<https://docs.cloud.google.com/api-gateway/docs/deployment-model>). El runtime de Apigee sí está en
  northamerica-south1 (<https://docs.cloud.google.com/apigee/docs/locations>) y su política VerifyJWT revisa la firma
  con la llave pública o un JWKS, la caducidad y, si se configuran, el emisor y la audiencia
  (<https://docs.cloud.google.com/apigee/docs/api-platform/reference/policies/verify-jwt-policy>). Por eso la respuesta
  es Apigee, el requisito de GCP pide que la pieza corra en la región de México y API Gateway queda como distractor.
- **Slot 3:** solo KMS de AWS registra cada uso sin configurar nada, en CloudTrail. Key Vault necesita activar su
  registro, Cloud KMS los registros de Data Access y OCI el registro de operaciones criptográficas; por eso el requisito
  dice "se puede registrar" (<https://learn.microsoft.com/en-us/azure/key-vault/general/logging>,
  <https://docs.cloud.google.com/kms/docs/audit-logging>,
  <https://docs.oracle.com/en-us/iaas/Content/Logging/Reference/details_for_kms.htm>).
- **Slot 4:** la operación desde una IP sospechosa está en las 4 nubes: GuardDuty con MaliciousIPCaller
  (<https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_finding-types-iam.html>), Defender for Resource Manager
  (<https://learn.microsoft.com/en-us/azure/defender-for-cloud/alerts-resource-manager>), Event Threat Detection con
  accesos desde la red Tor
  (<https://docs.cloud.google.com/security-command-center/docs/concepts-event-threat-detection-overview>) y Cloud Guard
  con Suspicious Ip Activity (<https://docs.oracle.com/en-us/iaas/cloud-guard/using/detect-recipes.htm>).
- **Azure:** AD B2C dejó de venderse a clientes nuevos el 1-may-2025, por eso aquí va Entra External ID. Entra ID
  Protection, que detecta riesgos de identidad, no está en la paleta y no está disponible en los tenants externos de
  External ID (<https://learn.microsoft.com/en-us/entra/external-id/customers/concept-supported-features-customers>).
- **GCP:** Event Threat Detection requiere el nivel Premium de Security Command Center.
- **OCI:** la rotación automática solo existe en una bóveda privada. Cloud Guard no documenta una regla de minería de
  criptomonedas, por eso el slot 4 ya no la pide
  (<https://docs.oracle.com/en-us/iaas/cloud-guard/using/detect-recipes.htm>).

---

## Escenario 6. Reservaciones en dos países

**Temas:** BD relacional con HA, réplicas de lectura, NoSQL multirregión y CAP, migración y secretos.
**Contexto:** MesaLista reserva mesas en 2 mil restaurantes de México y Texas. Los pagos piden transacciones y los
favoritos se escriben en ambos países.
**Topología:** dos regiones (México y EE. UU.), cada una con una VPC de 2 zonas y una subred privada. Los slots 1 y 2
están en México y el slot 3 en ambas regiones. Nodos fijos: servidores de app, el MySQL del restaurante piloto y el
equipo de reportes.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Pagos en MySQL administrado sin sacarlos de México, con una copia en otra zona (OCI: en otro dominio de falla) que toma el control sola si cae la primaria. | RDS for MySQL Multi-AZ | Azure Database for MySQL Flexible Server (HA con redundancia de zona) | Cloud SQL for MySQL (HA) | MySQL HeatWave (HA) | La réplica de lectura del mismo servicio, en las 4 nubes: es asíncrona y se promueve a mano. También Aurora Global Database (copia a otras regiones) / geo-replicación activa de Azure SQL / Spanner / Autonomous AI Database con Data Guard: sacan los datos de México o no son MySQL. | <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html> <https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-high-availability> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-read-replicas> <https://learn.microsoft.com/en-us/azure/azure-sql/database/active-geo-replication-overview> <https://docs.cloud.google.com/sql/docs/mysql/high-availability> <https://docs.cloud.google.com/sql/docs/mysql/replication> <https://docs.cloud.google.com/spanner/docs/true-time-external-consistency> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-high-availability.html> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html> <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-data-guard.html> |
| 2 | Los reportes leen de una copia aparte de la primaria del slot 1 para no frenarla, aunque lleve segundos de retraso. | réplica de lectura de RDS | réplica de lectura de Flexible Server | réplica de lectura de Cloud SQL | réplica de lectura de HeatWave | El standby de HA del mismo servicio, en las 4 nubes: no atiende lecturas (en AWS, el despliegue Multi-AZ DB instance). También Aurora Global Database / Azure SQL / Spanner / Autonomous AI Database: no son una copia del MySQL del slot 1. | <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-read-replicas> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-high-availability> <https://docs.cloud.google.com/sql/docs/mysql/replication> <https://docs.cloud.google.com/sql/docs/mysql/high-availability> <https://docs.cloud.google.com/spanner/docs/true-time-external-consistency> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-high-availability.html> <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-data-guard.html> |
| 3 | Los favoritos se escriben en milisegundos en la región de cada país y ambas aceptan escrituras. La otra región puede verlos después: se prefiere disponibilidad a consistencia. | DynamoDB global tables | Azure Cosmos DB (escrituras multirregión) | Bigtable (replicación) | Oracle NoSQL Database Cloud Service (Global Active Tables) | Aurora Global Database / geo-replicación activa de Azure SQL: escribe una sola región. Spanner: prioriza consistencia, la escritura espera. Autonomous AI Database con Data Guard: el standby no escribe. | <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html> <https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html> <https://learn.microsoft.com/en-us/azure/cosmos-db/multi-region-writes> <https://learn.microsoft.com/en-us/azure/azure-sql/database/active-geo-replication-overview> <https://docs.cloud.google.com/bigtable/docs/replication-overview> <https://docs.cloud.google.com/spanner/docs/true-time-external-consistency> <https://docs.cloud.google.com/bigtable/docs/locations> <https://docs.oracle.com/en/cloud/paas/nosql-cloud/gasnd/index.html> <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-data-guard.html> |
| 4 | Avisa al equipo de reportes si la copia del slot 2 se atrasa más de 30 segundos respecto a la primaria. | Amazon CloudWatch (alarma de ReplicaLag) | alertas de métricas de Azure Monitor (Replication Lag In Seconds) | alertas de Cloud Monitoring (replica_lag) | alarmas de OCI Monitoring | CloudTrail / registro de actividad / Cloud Audit Logs / Audit: registran acciones administrativas, no el retraso. | <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.Monitoring.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/creating_alarms.html> <https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-monitoring> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-read-replicas> <https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/activity-log> <https://docs.cloud.google.com/sql/docs/mysql/replication/replication-lag> <https://docs.cloud.google.com/monitoring/alerts> <https://docs.cloud.google.com/logging/docs/audit> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/metrics.html> <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Audit/Concepts/auditoverview.htm> |
| 5 | La contraseña de la BD no vive en el código: la app la pide al arrancar. AWS: una rotación programada en el mismo servicio la cambia cada 30 días. Azure: antes de que la contraseña venza, el servicio avisa para que una función propia la cambie. GCP: el servicio avisa cada 30 días que toca cambiarla, para que tu código la cambie. OCI: una rotación programada cada 30 días, con una función propia como destino, la cambia. | AWS Secrets Manager | Azure Key Vault (secretos) | Secret Manager | OCI Vault (secretos) | Parameter Store (no rota) / App Configuration (no guarda secretos) / Parameter Manager (no admite rotación) / bucket de Object Storage (la rotación programada es de los secretos de Vault). | <https://docs.aws.amazon.com/secretsmanager/latest/userguide/integrating_parameterstore.html> <https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotate-secrets_schedule.html> <https://learn.microsoft.com/en-us/azure/key-vault/secrets/tutorial-rotation> <https://learn.microsoft.com/en-us/azure/azure-app-configuration/overview> <https://docs.cloud.google.com/secret-manager/docs/secret-rotation> <https://docs.cloud.google.com/secret-manager/docs/release-notes> <https://docs.cloud.google.com/secret-manager/parameter-manager/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/secret-management/Tasks/create-secret.htm> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm> |

**Equivalencias:**

- **Slot 5:** solo AWS rota en forma nativa, por eso el requisito cambia por nube.
  - Azure necesita Event Grid y una Function. Key Vault publica el aviso 30 días antes del vencimiento, así que el
    requisito de Azure no fija los 30 días
    (<https://learn.microsoft.com/en-us/azure/key-vault/secrets/tutorial-rotation>).
  - GCP solo avisa por Pub/Sub y el cambio lo hace tu código
    (<https://docs.cloud.google.com/secret-manager/docs/secret-rotation>).
  - OCI rota solo con Autonomous AI Database o con una Function
    (<https://docs.oracle.com/en-us/iaas/Content/secret-management/Tasks/create-secret.htm>).
- **Slot 2 (AWS):** en un Multi-AZ DB cluster los standbys sí se pueden leer.
- **Slot 3:** DynamoDB es eventual por defecto, aunque ofrece consistencia fuerte multirregión. Cosmos DB con escrituras
  multirregión no admite Strong. Bigtable está en northamerica-south1 y us-south1
  (<https://docs.cloud.google.com/bigtable/docs/locations>).
- **Slot 4:** es el mismo retraso de réplica que el alumno ve en el visualizador del Lab 10.

---

## Escenario 7. Quiniela del Mundial 2026: solución completa

**Temas:** balanceo L7, contenedores sin servidores, caché, cola y NoSQL.
**Contexto:** una app mexicana espera 2 millones de jugadores durante los partidos del Mundial 2026, y las apuestas se
disparan en el minuto 90.
**Topología:** una región con una VPC y 2 zonas: el slot 1 en la subred pública y los slots 2 a 5 en la privada. Nodos
fijos: jugadores, internet y el proveedor de marcadores.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Es el proxy HTTP que recibe las apuestas por HTTPS, las reparte entre los contenedores y le pasa a la API la IP del jugador en el encabezado X-Forwarded-For. | Application Load Balancer | Azure Application Gateway (v2) | balanceador de aplicaciones externo regional | OCI Load Balancer (flexible) | NLB: capa 4, sin X-Forwarded-For. Azure Load Balancer: su grupo de back-end por IP solo admite VM o conjuntos de escalado, no PaaS. Balanceador de red de paso: no admite NEG sin servidores. Network Load Balancer: de paso, sin proxy. | <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/x-forwarded-headers.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html> <https://learn.microsoft.com/en-us/azure/application-gateway/overview> <https://learn.microsoft.com/en-us/azure/container-apps/waf-app-gateway> <https://learn.microsoft.com/en-us/azure/application-gateway/how-application-gateway-works> <https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview> <https://learn.microsoft.com/en-us/azure/load-balancer/backend-pool-management> <https://docs.cloud.google.com/load-balancing/docs/application-load-balancer> <https://docs.cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts> <https://docs.cloud.google.com/load-balancing/docs/https> <https://docs.oracle.com/en-us/iaas/Content/NetworkLoadBalancer/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendservers.htm> <https://docs.oracle.com/en-us/iaas/Content/Balance/Reference/httpheaders.htm> |
| 2 | La API corre en contenedores sin que el equipo de dos personas administre servidores, nodos ni un clúster de Kubernetes. | ECS en AWS Fargate | Azure Container Apps (entorno interno con VNet) | Cloud Run | OCI Container Instances | EKS con nodos EC2 / AKS / GKE Standard / OKE con nodos administrados: Kubernetes con nodos que opera el equipo. | <https://aws.amazon.com/fargate/faqs/> <https://docs.aws.amazon.com/eks/latest/userguide/eks-compute.html> <https://learn.microsoft.com/en-us/azure/container-apps/overview> <https://learn.microsoft.com/en-us/azure/aks/what-is-aks> <https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run> <https://docs.cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode> <https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc> <https://docs.oracle.com/en-us/iaas/Content/container-instances/overview-of-container-instances.htm> <https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengcomparingvirtualwithmanagednodes_topic.htm> |
| 3 | Guarda en memoria la tabla de posiciones de 2 millones de jugadores, ordenada por puntos, para no ir a la base de datos en cada consulta. | ElastiCache (Valkey) | Azure Managed Redis | Memorystore for Valkey | OCI Cache | Réplica de lectura de la BD relacional, en las 4 nubes: es otra copia de la base, no un almacén en memoria. | <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/SelectEngine.html> <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/elasticache-use-cases.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html> <https://learn.microsoft.com/en-us/azure/redis/overview> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-read-replicas> <https://docs.cloud.google.com/memorystore/docs/valkey/release-notes> <https://docs.cloud.google.com/memorystore/docs/valkey/client-library-code-samples> <https://cloud.google.com/memorystore> <https://docs.cloud.google.com/sql/docs/mysql/replication> <https://docs.oracle.com/en-us/iaas/Content/ocicache/home.htm> <https://docs.oracle.com/en-us/iaas/Content/ocicache/overview.htm> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html> |
| 4 | Absorbe el pico del minuto 90: los trabajadores sacan las apuestas a su ritmo y cada una se da por terminada solo cuando confirman que la procesaron; si no, se vuelve a entregar. | Amazon SQS (cola estándar) | Azure Service Bus (cola) | Pub/Sub (suscripción pull) | OCI Queue | Kinesis Data Streams / Event Hubs / Managed Kafka / OCI Streaming: cada consumidor lleva su posición y los mensajes no se borran al procesarse. | <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html> <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html> <https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html> <https://aws.amazon.com/kinesis/data-streams/faqs/> <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions> <https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-features> <https://docs.cloud.google.com/pubsub/docs/subscription-overview> <https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/edit-consumer-group> <https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/choose-kafka-pubsub> <https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview.htm> |
| 5 | Es la base de datos NoSQL de las apuestas: guarda cada una con clave por jugador y partido y solo la escribe si esa clave no existe, para que nadie apueste dos veces. | Amazon DynamoDB (una región) | Azure Cosmos DB (una región) | Firestore | Oracle NoSQL Database Cloud Service (una región) | S3 / Blob / Cloud Storage / Object Storage: almacenamiento de objetos, no base NoSQL. También la réplica de lectura de la BD relacional: no acepta escrituras. | <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html> <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html> <https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html> <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/S3DataExport.HowItWorks.html> <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html> <https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning> <https://learn.microsoft.com/en-us/rest/api/cosmos-db/create-a-document> <https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels> <https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction> <https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-read-replicas> <https://docs.cloud.google.com/firestore/native/docs/overview> <https://docs.cloud.google.com/firestore/docs/reference/rest/v1/Precondition> <https://docs.cloud.google.com/storage/docs/objects> <https://docs.cloud.google.com/sql/docs/mysql/replication> <https://docs.oracle.com/en/cloud/paas/nosql-cloud/dtddt/designing-a-table-in-oracle-nosql-database-cloud-service.html> <https://docs.oracle.com/en/cloud/paas/nosql-cloud/dtddt/using-apis-to-add-table-data.html> <https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm> <https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html> |

**Equivalencias:**

- **Por qué capa 7:** con balanceo de capa 4 la arquitectura no se monta en dos nubes. Azure Load Balancer no acepta
  Container Apps como back-end (<https://learn.microsoft.com/en-us/azure/load-balancer/backend-pool-management>) y los
  balanceadores de red de paso de GCP no admiten NEG sin servidores
  (<https://docs.cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts>). Con capa 7 se conservan la
  topología y los slots 2 a 5, y cada balanceador de capa 4 queda como distractor.
- **Slot 1:** los 4 proxies entregan la IP del jugador en X-Forwarded-For, y OCI también la pone en X-Real-IP
  (<https://docs.oracle.com/en-us/iaas/Content/Balance/Reference/httpheaders.htm>).
- **Azure (slots 1 y 2):** la guía oficial pone Application Gateway frente a Container Apps en un entorno interno
  integrado a la VNet (<https://learn.microsoft.com/en-us/azure/container-apps/waf-app-gateway>).
- **GCP (slots 1 y 2):** los NEG sin servidores no llevan health check, por eso el requisito 1 no dice "solo entre
  destinos sanos". Cloud Run vive fuera de la VPC y se dibuja en la subred privada por simplificación
  (<https://docs.cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts>).
- **OCI (slot 1):** el Load Balancer registra sus backends por OCID o por IP
  (<https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendservers.htm>); que el backend sea la IP
  privada de la instancia de contenedor es deducción (ver "No verificado").
- **GCP (slot 4):** la cola es una suscripción pull de Pub/Sub.
- **Slot 5:** la escritura condicional está documentada en las 4 nubes: `attribute_not_exists` en DynamoDB
  (<https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html>), 409
  Conflict en Cosmos DB (<https://learn.microsoft.com/en-us/rest/api/cosmos-db/create-a-document>), la precondición
  `exists=false` en Firestore (<https://docs.cloud.google.com/firestore/docs/reference/rest/v1/Precondition>) e
  `IfAbsent` en Oracle NoSQL
  (<https://docs.oracle.com/en/cloud/paas/nosql-cloud/dtddt/using-apis-to-add-table-data.html>). El requisito ya no dice
  "millones por minuto": Firestore recomienda empezar con 500 operaciones por segundo y subir 50 % cada 5 minutos
  (<https://docs.cloud.google.com/firestore/native/docs/best-practices>), y la cola del slot 4 marca ese ritmo.

---

## Escenario 8. Paquetería (mensajería: publicar/suscribir, cola, entrega al menos una vez, DLQ y streaming)

**Contexto:** EnvíaYa reparte 80 mil paquetes al día en el Bajío. Cada "pedido creado" llega a facturación, al SMS del
cliente y a la asignación de repartidor, y una falla en uno no detiene a los demás.
**Topología:** API (fija) → slot 1 → {SMS (fijo), slot 2 → slot 3 → slot 4}. Aparte, el GPS de los repartidores llega al
slot 5, que lee analítica (fija).

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Un mismo "pedido creado" llega a varios consumidores independientes, sin que la API sepa cuántos son. OCI: el servicio envía por sí mismo el SMS al cliente y entrega el pedido a otros suscriptores. | Amazon SNS (tema) | Service Bus (tema y suscripciones) | tema de Pub/Sub | OCI Notifications (tema) | SQS / cola de Service Bus: un solo consumidor por mensaje (lo contrasta la explicación, sin tarjeta distractora). Cloud Tasks (GCP): entrega cada tarea al endpoint que elige el publicador. OCI Streaming: los consumidores leen por offset y no entrega SMS. | <https://docs.aws.amazon.com/sns/latest/dg/sns-sqs-as-subscriber.html> <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions> <https://docs.cloud.google.com/tasks/docs/comp-pub-sub> <https://docs.oracle.com/en-us/iaas/Content/Notification/Concepts/notificationoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview.htm> |
| 2 | Recibe su copia de cada pedido y la guarda hasta que un trabajador confirma que la procesó; si el trabajador muere a la mitad, el pedido reaparece. | cola estándar de SQS | cola de Service Bus (destino del reenvío) | suscripción push de Pub/Sub | OCI Queue | ElastiCache / Managed Redis / Memorystore / OCI Cache: son cachés en memoria, sin garantía de entrega. GCP: también Cloud Tasks, que no recibe copias de un tema. | <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html> <https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html> <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-auto-forwarding> <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions> <https://docs.cloud.google.com/pubsub/docs/subscription-overview> <https://docs.cloud.google.com/tasks/docs/comp-pub-sub> <https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm> |
| 3 | El código que asigna repartidor solo corre cuando hay mensajes, escala solo y no cuesta de madrugada. | AWS Lambda (mapeo de eventos SQS) | Azure Functions (disparador de Service Bus, plan Flex Consumption) | Cloud Run (suscripción push) | OCI Functions (vía Connector Hub) | EC2 / Virtual Machines / Compute Engine / Compute: cobran mientras están encendidas. OCI: también Connector Hub, que mueve los mensajes pero no corre el código. | <https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html> <https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-service-bus-trigger> <https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan> <https://learn.microsoft.com/en-us/azure/azure-functions/functions-target-based-scaling> <https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table> <https://docs.cloud.google.com/run/docs/triggering/pubsub-push> <https://docs.oracle.com/en-us/iaas/Content/connector-hub/overview.htm> |
| 4 | Un pedido que falla 5 veces se aparta solo para revisarlo después, sin bloquear la fila. OCI: aparta el pedido que falla 5 veces para revisarlo después, para que no se reintente sin fin. | DLQ de SQS (redrive) | subcola de mensajes fallidos (dead-letter) de Service Bus | tema de mensajes fallidos (dead-letter) de Pub/Sub | DLQ de OCI Queue | Bucket S3 / contenedor Blob / bucket / bucket: guardan, pero no cuentan intentos ni apartan el mensaje por sí solos. | <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html> <https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html> <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues> <https://docs.cloud.google.com/pubsub/docs/handling-failures> <https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/connector-hub/queue-to-function.htm> |
| 5 | El GPS se conserva 7 días en orden (GCP: 90 días) y analítica lo relee desde el principio cuantas veces quiera. | Kinesis Data Streams | Azure Event Hubs | Managed Service for Apache Kafka | OCI Streaming | Data Firehose (entrega a un destino) / Stream Analytics (no guarda la entrada) / Dataflow (procesa en tránsito) y tema o suscripción de Pub/Sub (retienen 31 días como máximo) / Connector Hub (mueve datos): ninguno conserva el GPS para releerlo. | <https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html> <https://docs.aws.amazon.com/firehose/latest/dev/basic-deliver.html> <https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-features> <https://learn.microsoft.com/en-us/azure/stream-analytics/stream-analytics-introduction> <https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/overview> <https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/create-topic> <https://kafka.apache.org/intro> <https://docs.cloud.google.com/pubsub/docs/create-topic> <https://docs.cloud.google.com/pubsub/docs/subscription-properties> <https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/connector-hub/overview.htm> |

**Equivalencias:**

- **OCI cambia la topología.** Notifications no entrega a Queue, así que entre los slots 1 y 2 va una Function que
  encola. El slot 3 se conecta con Connector Hub, con Queue como origen y Functions como destino.
- **OCI (slot 1):** con el texto común, Streaming con varios grupos de consumidores también cumplía. Por eso el
  requisito de OCI pide que el servicio envíe el SMS por sí mismo: SMS es un protocolo de suscripción de Notifications
  (<https://docs.oracle.com/en-us/iaas/Content/Notification/Concepts/notificationoverview.htm>).
- **Azure y GCP (slot 1):** Service Bus y Pub/Sub no envían SMS; lo hace un consumidor de la suscripción. Por eso la
  flecha del tema a "Clientes (SMS)" dice "SMS vía código propio"
  (<https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions>,
  <https://docs.cloud.google.com/pubsub/docs/subscription-overview>). En AWS el tema de SNS sí entrega por SMS a los
  números suscritos (<https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-phone-number-as-subscriber.html>), y en OCI
  también, con Notifications.
- **Azure (slot 3):** la tabla de productos por región marca en Mexico Central el plan Consumo de Linux de Functions
  como en cierre ("Closing Down"), y Flex Consumption y el plan Consumo como GA
  (<https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table>). Por eso la explicación
  nombra Flex Consumption, el plan sin servidor recomendado: escala a cero, cobra por ejecución
  (<https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan>) y escala según los mensajes
  pendientes de Service Bus (<https://learn.microsoft.com/en-us/azure/azure-functions/functions-target-based-scaling>).
- **AWS (slot 4):** la función usa ReportBatchItemFailures para que solo el pedido que falla vuelva a la cola y sume
  recepciones; sin eso, todo el lote vuelve a la cola
  (<https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html>).
- **OCI (slot 4):** Connector Hub no admite fallas parciales de un lote de Queue a Functions: todo el lote vuelve a la
  cola, suma una entrega y el conector reintenta hasta que la función responda bien. Por eso el requisito de OCI pide
  que el pedido no se reintente sin fin y la explicación pide lotes de 1 mensaje en el conector
  (<https://docs.oracle.com/en-us/iaas/Content/connector-hub/queue-to-function.htm>).
- **Azure (slot 2):** el reenvío automático se configura en la suscripción del tema (origen) hacia la cola, y Service
  Bus no deja crear receptores en un origen con reenvío activo, así que Functions lee de la cola destino. La flecha dice
  "reenvío de la suscripción"
  (<https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-auto-forwarding>).
- **GCP:** los slots 1 y 2 son recursos de Pub/Sub: el tema y su suscripción push hacia Cloud Run. El nodo fijo "API de
  pedidos" usa el icono de Apigee, como el slot 2 del escenario 5, porque API Gateway no se despliega en México
  (<https://docs.cloud.google.com/api-gateway/docs/deployment-model>).
- **GCP (slot 5):** pide 90 días en lugar de 7 para dejar fuera a Pub/Sub, que retiene 31 días como máximo en el tema y
  en la suscripción (<https://docs.cloud.google.com/pubsub/docs/create-topic>,
  <https://docs.cloud.google.com/pubsub/docs/subscription-properties>).
- **Entrega al menos una vez:** el slot 2 puede entregar un pedido dos veces si el trabajador muere después de
  procesarlo y antes de confirmarlo. El trabajador debe ser idempotente: asignar el mismo pedido dos veces no puede
  generar dos repartidores. Es el mismo duplicado que el alumno provoca en el Lab 14.

---

## Escenario 9 (Actividad 9). El DNS elige la región y el balanceador elige la instancia

**Origen:** Lab 04, `lab04-dns-plus-load-balancer-multi-region.drawio`. Route 53 (latencia, TTL de 60 s) responde con el
ALB de us-east-1 o el de eu-west-1. Cada ALB reparte entre su grupo de Auto Scaling, y si cae una región el DNS conmuta.

**Por qué este lab:**

- **Combina 4 temas:** DNS, balanceo, autoescalado y alta disponibilidad multirregión.
- **Muestra dos tiempos de recuperación:** minutos por el TTL y segundos en el balanceador.
- **No repite ningún escenario:** ninguno de los 8 conmuta regiones por DNS.
- **Funciona en las 4 nubes:** todas tienen DNS con health checks hacia endpoints públicos.

Se descartaron:

- **Lab 01:** Cloud Map y ECS vienen integrados en Container Apps y Cloud Run, sin huecos limpios.
- **Lab 08:** su subred por AZ y su internet gateway no existen en Azure ni GCP, y se parece al escenario 1.
- **Lab 06:** Keycloak es software, no un servicio de nube, y se cruza con el escenario 5.

**Contexto:** una tienda vende a México y España con un solo dominio, `tienda.mx`; si cae una región, los compradores
deben llegar a la otra en minutos. Regiones: mx-central-1 y eu-south-2 (AWS), Mexico Central y Spain Central (Azure),
northamerica-south1 y europe-southwest1 (GCP), Querétaro y Madrid (OCI, donde Querétaro es la región principal).
**Topología (la del lab):** visitante → slot 1 → región A (slot 3 → slot 4, con las VM fijas) y región B (slot 6 → slot
7, con las VM fijas). Cada región tiene una VPC de 2 zonas. El slot 2 vigila cada región y el slot 5 avisa al equipo.

| slot | requisito | AWS | Azure | GCP | OCI | distractor por nube | fuente(s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Publica un solo nombre, `tienda.mx`, y responde con la dirección de la región sana más cercana al comprador, con un TTL de 60 s. OCI: responde con la región A mientras esté sana y, si no, con la B. | Route 53 (zona pública, latencia) | Azure Traffic Manager | Cloud DNS (zona pública con políticas de enrutamiento) | steering policies de OCI Traffic Management | Route 53 VPC Resolver / DNS Private Resolver / políticas de servidor de Cloud DNS / resolver privado: resuelven dentro de la red, no publican. | <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-types.html> <https://aws.amazon.com/route53/vpc-resolver/> <https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-routing-methods> <https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-how-it-works> <https://learn.microsoft.com/en-us/azure/dns/dns-private-resolver-overview> <https://docs.cloud.google.com/dns/docs/routing-policies-overview> <https://docs.cloud.google.com/dns/docs/policies-overview> <https://docs.oracle.com/en-us/iaas/Content/TrafficManagement/Concepts/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/DNS/Tasks/privatedns.htm> |
| 2 | Desde varios puntos de internet prueba, cada cierto intervalo, que el balanceador de cada región responda; si una falla, el slot 1 deja de anunciarla. | health checks de Route 53 | monitoreo de endpoints (integrado en el perfil de Traffic Manager) | health checks de Cloud DNS (endpoints externos) | OCI Health Checks | Health check del target group / sondeo de Application Gateway / health check del backend service / health check del backend set: los hace el balanceador sobre sus propios destinos, no los health checks que consulta el DNS. | <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/monitoring-health-checks.html> <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-types.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-how-it-works> <https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-routing-methods> <https://learn.microsoft.com/en-us/azure/application-gateway/overview> <https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-probe-overview> <https://docs.cloud.google.com/dns/docs/zones/manage-routing-policies> <https://docs.cloud.google.com/dns/docs/routing-policies-overview> <https://docs.cloud.google.com/load-balancing/docs/https> <https://docs.oracle.com/en-us/iaas/Content/HealthChecks/Concepts/healthchecks.htm> <https://docs.oracle.com/en-us/iaas/Content/TrafficManagement/Concepts/overview.htm> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingcertificates.htm> |
| 3 | En la región A recibe el HTTPS, termina TLS y reparte las peticiones solo entre las VM web que pasan su revisión de salud. | Application Load Balancer | Application Gateway v2 | balanceador de aplicaciones externo regional | OCI Load Balancer | API Gateway / API Management / API Gateway / API Gateway: sirven para crear, publicar, administrar o proteger APIs; el slot pide un balanceador de capa 7 que termine TLS y reparta entre las VM sanas. | <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html> <https://learn.microsoft.com/en-us/azure/application-gateway/overview> <https://learn.microsoft.com/en-us/azure/api-management/api-management-key-concepts> <https://docs.cloud.google.com/load-balancing/docs/https> <https://docs.cloud.google.com/api-gateway/docs/about-api-gateway> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingcertificates.htm> <https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayoverview.htm> |
| 4 | Mantiene al menos 2 VM web de la región A en zonas distintas, reemplaza la que falla y agrega más cuando sube la carga. OCI: administra como grupo las VM web, repartidas en dominios de falla, y crece o se reduce con la carga. | EC2 Auto Scaling (grupo) | Virtual Machine Scale Sets | MIG (grupo de instancias administrado) | instance pool con autoscaling | Launch template / availability set / grupo no administrado / instance configuration: son plantillas o reparto, no escalan. También la VM sola (EC2 / Virtual Machines / Compute Engine / Compute), que ya está en el diagrama. | <https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-health-checks.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://docs.aws.amazon.com/autoscaling/ec2/userguide/launch-templates.html> <https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-autoscale-overview> <https://learn.microsoft.com/en-us/azure/virtual-machines/availability-set-overview> <https://docs.cloud.google.com/compute/docs/instance-groups/autohealing-instances-in-migs> <https://docs.cloud.google.com/compute/docs/autoscaler> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instancemanagement.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/autoscalinginstancepools.htm> |
| 5 | Le entrega a guardia el aviso de la alarma cuando el slot 2 marca caída una región; desde ese aviso corre el tiempo de reparación. | Amazon SNS (tema, desde una alarma de CloudWatch) | grupos de acciones de Azure Monitor | canales de notificación de Cloud Monitoring | OCI Notifications (tema) | CloudWatch Logs / Log Analytics / Cloud Logging / Logging: guardan y consultan registros; el aviso a guardia sale por el servicio de notificaciones. | <https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/monitoring-health-checks.html> <https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html> <https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups> <https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-workspace-overview> <https://docs.cloud.google.com/monitoring/support/notification-options> <https://docs.cloud.google.com/logging/docs/overview> <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm> <https://docs.oracle.com/en-us/iaas/Content/Logging/Concepts/loggingoverview.htm> |
| 6 | En la región B hace lo mismo que el slot 3 en la A. | Application Load Balancer | Application Gateway v2 | balanceador de aplicaciones externo regional | OCI Load Balancer | Los mismos del slot 3. | <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html> <https://learn.microsoft.com/en-us/azure/application-gateway/overview> <https://learn.microsoft.com/en-us/azure/api-management/api-management-key-concepts> <https://docs.cloud.google.com/load-balancing/docs/https> <https://docs.cloud.google.com/api-gateway/docs/about-api-gateway> <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingcertificates.htm> <https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayoverview.htm> |
| 7 | En la región B hace lo mismo que el slot 4 en la A. | EC2 Auto Scaling (grupo) | Virtual Machine Scale Sets | MIG | instance pool con autoscaling | Los mismos del slot 4. | <https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-health-checks.html> <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html> <https://docs.aws.amazon.com/autoscaling/ec2/userguide/launch-templates.html> <https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-autoscale-overview> <https://learn.microsoft.com/en-us/azure/virtual-machines/availability-set-overview> <https://docs.cloud.google.com/compute/docs/instance-groups/autohealing-instances-in-migs> <https://docs.cloud.google.com/compute/docs/autoscaler> <https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instancemanagement.htm> <https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/autoscalinginstancepools.htm> |

**Equivalencias:**

- **Azure:** el monitoreo viene dentro de Traffic Manager. El slot 2 es el monitoreo de endpoints del perfil, una pieza
  del perfil y no un servicio aparte
  (<https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-how-it-works>).
- **AWS (slot 2):** con registros alias, Route 53 puede usar Evaluate Target Health en lugar de un health check propio,
  y la salud del ALB sale de sus target groups. Por eso el distractor contrasta quién prueba: el balanceador sobre sus
  destinos frente a los health checkers de Route 53
  (<https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-types.html>).
- **GCP:** los health checks hacia endpoints externos solo funcionan en zonas públicas y exigen desactivar la política
  `constraints/compute.disableInternetNetworkEndpointGroup`. El balanceador global no se usa porque reemplazaría al DNS
  por una IP anycast.
- **OCI:** documenta health checks solo para las políticas de failover y de balanceo, por eso su slot 1 usa failover. La
  guía de Health Checks solo nombra monitores HTTP y ping, así que el requisito 2 pide que el balanceador "responda",
  sin decir HTTPS (<https://docs.oracle.com/en-us/iaas/Content/HealthChecks/Concepts/healthchecks.htm>).
- **TTL no es MTTR:** el tiempo de recuperación suma la detección del slot 2, el TTL del slot 1, la caché DNS del
  cliente y la reconexión. Por eso no se promete una recuperación igual al TTL.

---

## Equivalencias dudosas

### Sin equivalente limpio

- **E3-1 OCI:** no tiene CDN; usa la caché regional del balanceador (Web Application Acceleration), que no guarda los
  videos. En OCI la flecha del slot 1 al slot 2 es punteada y los videos salen directo de Object Storage.
- **E3-3 Azure:** Mexico Central no ofrece el nivel Archive de Blob Storage; usa Cold, el nivel más barato por GB de la
  región (<https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table>).
- **E5-2 GCP:** API Gateway no se despliega en México; usa Apigee, cuyo runtime sí está en northamerica-south1
  (<https://docs.cloud.google.com/api-gateway/docs/deployment-model>,
  <https://docs.cloud.google.com/apigee/docs/locations>).
- **E7-1 Azure y GCP:** el balanceo de capa 4 no llega a los contenedores sin servidores; el escenario usa capa 7.
- **E8-1→2 OCI:** Notifications no entrega a Queue; agrega una Function y Connector Hub.
- **E9-1/2 Azure:** el health check viene integrado en el DNS.
- **E6-5 Azure, GCP y OCI:** la rotación de secretos requiere código propio.
- **E1-1 Azure y GCP:** no tienen internet gateway como recurso.
- **E7-4 y E8-1/2 GCP:** la cola es una suscripción de Pub/Sub.

### No verificado

- **Almacenamiento:** el erasure coding en AWS y Azure, y la redundancia por zona de OCI Object Storage.
- **Distractores de AWS:** que Firehose no deja releer (deducido).
- **E2-2 OCI:** que un instance pool reemplace por sí solo una instancia que falla una revisión de salud; solo está
  documentado que crea otra cuando se termina una
  (<https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/instance-pools.htm>).
- **E2-4 OCI:** que OCI Certificates no emita certificados públicos. La página general habla de importar certificados de
  una CA externa y de emitir desde CA propias, pero no lo dice; los puzzles no lo afirman
  (<https://docs.oracle.com/en-us/iaas/Content/certificates/overview.htm>).
- **E6-4 OCI:** el nombre y la unidad de la métrica de retraso de réplica de HeatWave. La guía de réplicas la menciona,
  pero la tabla de métricas no la lista
  (<https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-read-replica.html>,
  <https://docs.oracle.com/en-us/iaas/mysql-database/doc/metrics.html>).
- **E7-1 OCI:** ninguna página documenta una Container Instance como backend del Load Balancer. Se infiere de que el
  balanceador registra backends por IP y de que la instancia recibe una IP privada en su subred
  (<https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendservers.htm>,
  <https://docs.oracle.com/en-us/iaas/Content/container-instances/creating-a-container-instance.htm>).
- **E7-1 GCP:** ninguna página lista el balanceador de aplicaciones externo regional por región; se infiere de que es
  Standard Tier y ese nivel existe en todas las regiones (<https://docs.cloud.google.com/network-tiers/docs/overview>).
- **OCI:** la geolocalización con health checks (E9 usa failover, que sí los documenta) y la duración máxima de una
  sesión de Bastion.

**Evitados por retiro:** Azure Cache for Redis (2027-2028), Front Door classic (31-mar-2027), AD B2C (sin clientes
nuevos desde el 1-may-2025) y el WAF de borde de OCI (legacy).
