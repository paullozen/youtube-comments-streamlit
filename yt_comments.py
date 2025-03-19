import streamlit as st
import time
import googleapiclient.discovery
import re
import zipfile
import os

def get_channel_id_from_handle(api_key, handle):
    """Obtém o channel_id a partir do @handle do canal"""
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    request = youtube.search().list(
        part="snippet",
        q=handle,
        type="channel",
        maxResults=1
    )
    response = request.execute()

    if 'items' in response and len(response['items']) > 0:
        return response['items'][0]['id']['channelId']
    else:
        raise Exception("Não foi possível encontrar o canal para o handle fornecido.")

def get_channel_video_ids(api_key, channel_id, max_results=50, order_by_popularity=False):
    """Obtém os IDs dos vídeos do canal"""
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    request = youtube.search().list(
        part="id",
        channelId=channel_id,
        maxResults=max_results,
        order="viewCount" if order_by_popularity else "date"
    )
    response = request.execute()

    video_ids = [item['id']['videoId'] for item in response.get('items', [])]
    return video_ids

def clean_comment(comment):
    """Remove links HTML como [<a href="...">10:00</a>] do comentário"""
    return re.sub(r'<a href=".*?">.*?</a>', '', comment).strip()

def get_video_comments(api_key, video_id, max_results=5000):
    """Obtém os comentários de um vídeo com barra de progresso"""
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    comments = []
    next_page_token = None
    output_file = f"{video_id}.txt"

    progress_bar = st.progress(0)
    collected_comments = 0

    with open(output_file, "w", encoding="utf-8") as f:
        while len(comments) < max_results:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                cleaned_comment = clean_comment(comment)  # Remove links antes de salvar
                comments.append(cleaned_comment)
                f.write(cleaned_comment + "\n")

                collected_comments += 1

                # Atualiza barra de progresso
                progress = min(1.0, collected_comments / max_results)
                progress_bar.progress(progress)

                if len(comments) >= max_results:
                    break

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

    progress_bar.empty()  # Remove a barra de progresso ao final
    return output_file, len(comments)

def extract_video_id(video_url):
    """Extrai o video_id a partir da URL"""
    match = re.search(r"v=([a-zA-Z0-9_-]{11})", video_url)
    return match.group(1) if match else None

def zip_files(file_list, zip_filename="comentarios_coletados.zip"):
    """Cria um único arquivo ZIP contendo todos os arquivos coletados"""
    with zipfile.ZipFile(zip_filename, "w") as zipf:
        for file in file_list:
            zipf.write(file)
    return zip_filename

# Configuração do Streamlit
st.title("Coletor de Comentários do YouTube")

# Entrada para chave da API
api_key = st.text_input("Insira sua chave da API do YouTube", type="password")

# Escolha entre canal ou vídeo
modo = st.radio("Escolha o modo de coleta", ["Canal", "Vídeo"])

if modo == "Canal":
    channel_handle = st.text_input("Digite o @handle do canal", "@nomeDoCanal")
    order_by_popularity = st.checkbox("Ordenar por popularidade?", value=True)
    max_results_videos = st.number_input("Quantidade de vídeos para coletar", min_value=1, max_value=100, value=20)
    max_comments_per_video = st.number_input("Quantidade de comentários por vídeo", min_value=10, max_value=5000, value=2000)
else:
    video_url = st.text_input("Cole o link do vídeo", "https://www.youtube.com/watch?v=xxxxxxxxxxx")

# Botão para iniciar a coleta
if st.button("Iniciar Coleta"):
    if not api_key:
        st.error("Por favor, insira sua chave da API do YouTube.")
    else:
        if modo == "Canal":
            try:
                st.write(f"Buscando ID do canal para {channel_handle}...")
                channel_id = get_channel_id_from_handle(api_key, channel_handle)
                st.write(f"ID do canal encontrado: {channel_id}")

                st.write("Buscando vídeos do canal...")
                video_ids = get_channel_video_ids(api_key, channel_id, max_results_videos, order_by_popularity)
                st.write(f"Vídeos coletados: {video_ids}")

                arquivos = []
                for i, video_id in enumerate(video_ids):
                    st.write(f"Coletando comentários do vídeo {i+1}/{len(video_ids)}: {video_id}")
                    output_file, num_comments = get_video_comments(api_key, video_id, max_comments_per_video)
                    arquivos.append(output_file)
                    st.success(f"Coletados {num_comments} comentários para o vídeo {video_id}.")

                    time.sleep(2)

                st.success("Coleta finalizada!")

                if arquivos:
                    zip_filename = zip_files(arquivos)
                    with open(zip_filename, "rb") as f:
                        st.download_button(
                            label="Baixar Todos os Arquivos (ZIP)",
                            data=f,
                            file_name=zip_filename,
                            mime="application/zip"
                        )

            except Exception as e:
                st.error(f"Erro: {e}")

        elif modo == "Vídeo":
            video_id = extract_video_id(video_url)
            if not video_id:
                st.error("URL inválida! Certifique-se de que está no formato correto.")
            else:
                st.write(f"ID do vídeo encontrado: {video_id}")
                st.write("Iniciando coleta de comentários...")
                output_file, num_comments = get_video_comments(api_key, video_id, 5000)  # Sempre coleta o máximo

                st.success(f"Coletados {num_comments} comentários para o vídeo.")

                # Botão para download do arquivo
                with open(output_file, "rb") as f:
                    st.download_button(
                        label="Baixar arquivo de comentários",
                        data=f,
                        file_name=output_file,
                        mime="text/plain"
                    )
