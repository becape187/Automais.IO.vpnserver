"""
Dashboard HTML em tempo real do WireGuard
"""
from config import VPN_SERVER_NAME


def get_dashboard_html() -> str:
    """Retorna HTML completo do dashboard"""
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WireGuard Dashboard - {VPN_SERVER_NAME or "VPN Server"}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            color: #667eea;
            font-size: 28px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }}
        .status-online {{
            background: #10b981;
            color: white;
        }}
        .status-offline {{
            background: #ef4444;
            color: white;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            color: #667eea;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }}
        .stat-card .label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        .interfaces {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .interface {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .interface-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .interface-name {{
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }}
        .peer {{
            background: #f9fafb;
            border-left: 3px solid #667eea;
            padding: 12px;
            margin-top: 10px;
            border-radius: 4px;
        }}
        .peer-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .peer-key {{
            font-family: monospace;
            font-size: 12px;
            color: #666;
            word-break: break-all;
        }}
        .peer-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            font-size: 13px;
        }}
        .peer-info-item {{
            color: #666;
        }}
        .peer-info-item strong {{
            color: #333;
        }}
        .refresh-indicator {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 10px 15px;
            border-radius: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            font-size: 12px;
            color: #666;
        }}
        .loading {{
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 18px;
        }}
        .error {{
            background: #fee2e2;
            color: #991b1b;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .pulsing {{
            animation: pulse 2s infinite;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🔒 WireGuard Dashboard</h1>
                <p style="color: #666; margin-top: 5px;">Instância: <strong>{VPN_SERVER_NAME or "Não configurado"}</strong></p>
            </div>
            <div class="refresh-indicator" id="refreshIndicator">
                ⏱️ Atualizando...
            </div>
        </div>

        <div id="loading" class="loading">
            <div class="pulsing">🔄 Carregando dados...</div>
        </div>

        <div id="error" style="display: none;"></div>

        <div id="content" style="display: none;">
            <div class="stats-grid" id="statsGrid"></div>
            <div class="interfaces" id="interfaces"></div>
        </div>
    </div>

    <script>
        let refreshInterval;
        const REFRESH_INTERVAL = 3000; // 3 segundos

        async function fetchStatus() {{
            try {{
                const response = await fetch('/api/v1/vpn/status');
                if (!response.ok) throw new Error('Erro ao buscar status');
                const data = await response.json();
                updateDashboard(data);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
                document.getElementById('error').style.display = 'none';
            }} catch (error) {{
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').innerHTML = `
                    <div class="error">
                        <strong>❌ Erro:</strong> ${{error.message}}
                        <br><small>Tentando novamente em alguns segundos...</small>
                    </div>
                `;
            }}
        }}

        function updateDashboard(data) {{
            // Atualizar indicador de refresh
            const now = new Date();
            document.getElementById('refreshIndicator').textContent = 
                `🔄 Atualizado: ${{now.toLocaleTimeString('pt-BR')}}`;

            // Atualizar estatísticas
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <h3>Interfaces</h3>
                    <div class="value">${{data.total_interfaces || 0}}</div>
                    <div class="label">Total de interfaces ativas</div>
                </div>
                <div class="stat-card">
                    <h3>Peers</h3>
                    <div class="value">${{data.total_peers || 0}}</div>
                    <div class="label">Total de peers conectados</div>
                </div>
                <div class="stat-card">
                    <h3>Download</h3>
                    <div class="value">${{data.total_rx_formatted || '0 B'}}</div>
                    <div class="label">Total recebido</div>
                </div>
                <div class="stat-card">
                    <h3>Upload</h3>
                    <div class="value">${{data.total_tx_formatted || '0 B'}}</div>
                    <div class="label">Total enviado</div>
                </div>
            `;

            // Atualizar interfaces
            const interfacesDiv = document.getElementById('interfaces');
            if (!data.interfaces || data.interfaces.length === 0) {{
                interfacesDiv.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">Nenhuma interface WireGuard encontrada.</p>';
                return;
            }}

            interfacesDiv.innerHTML = '<h2 style="margin-bottom: 20px; color: #667eea;">Interfaces WireGuard</h2>';
            
            data.interfaces.forEach(iface => {{
                const onlinePeers = iface.peers.filter(p => p.status === 'online').length;
                const totalPeers = iface.peers.length;
                
                let interfaceHtml = `
                    <div class="interface">
                        <div class="interface-header">
                            <div>
                                <span class="interface-name">${{iface.name}}</span>
                                <span class="status-badge ${{onlinePeers > 0 ? 'status-online' : 'status-offline'}}" style="margin-left: 10px;">
                                    ${{onlinePeers}}/${{totalPeers}} Online
                                </span>
                            </div>
                            <div style="font-size: 12px; color: #666;">
                                Porta: ${{iface.listen_port || 'N/A'}}
                            </div>
                        </div>
                `;

                if (iface.peers.length === 0) {{
                    interfaceHtml += '<p style="color: #666; margin-top: 10px;">Nenhum peer configurado.</p>';
                }} else {{
                    iface.peers.forEach(peer => {{
                        const isOnline = peer.status === 'online';
                        const rxFormatted = formatBytes(peer.transfer_rx || 0);
                        const txFormatted = formatBytes(peer.transfer_tx || 0);
                        const handshake = peer.latest_handshake ? 
                            new Date(peer.latest_handshake).toLocaleString('pt-BR') : 
                            'Nunca';

                        interfaceHtml += `
                            <div class="peer">
                                <div class="peer-header">
                                    <span class="status-badge ${{isOnline ? 'status-online' : 'status-offline'}}">
                                        ${{isOnline ? '🟢 Online' : '🔴 Offline'}}
                                    </span>
                                </div>
                                <div class="peer-key">${{peer.public_key.substring(0, 44)}}...</div>
                                <div class="peer-info">
                                    <div class="peer-info-item">
                                        <strong>IPs Permitidos:</strong><br>
                                        ${{peer.allowed_ips.join(', ') || 'N/A'}}
                                    </div>
                                    <div class="peer-info-item">
                                        <strong>Último Handshake:</strong><br>
                                        ${{handshake}}
                                    </div>
                                    <div class="peer-info-item">
                                        <strong>Download:</strong><br>
                                        ${{rxFormatted}}
                                    </div>
                                    <div class="peer-info-item">
                                        <strong>Upload:</strong><br>
                                        ${{txFormatted}}
                                    </div>
                                    ${{peer.endpoint ? `
                                    <div class="peer-info-item">
                                        <strong>Endpoint:</strong><br>
                                        ${{peer.endpoint}}
                                    </div>
                                    ` : ''}}
                                </div>
                            </div>
                        `;
                    }});
                }}

                interfaceHtml += '</div>';
                interfacesDiv.innerHTML += interfaceHtml;
            }});
        }}

        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }}

        // Iniciar atualização automática
        fetchStatus();
        refreshInterval = setInterval(fetchStatus, REFRESH_INTERVAL);

        // Atualizar ao focar na janela
        window.addEventListener('focus', fetchStatus);
    </script>
</body>
</html>
"""

