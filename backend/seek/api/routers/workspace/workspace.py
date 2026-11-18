"""用户工作区文件读写、上传和授权下载路由。"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from seek.api.dependencies.auth import get_db, get_required_user
from seek.api.responses.files import render_file_result
from seek.api.uploads import prepare_upload_files
from seek.modules.identity.models import User
from seek.modules.workspace.services.files import (
    MAX_WORKSPACE_UPLOAD_SIZE_BYTES,
    create_workspace_directory,
    delete_workspace_path,
    download_workspace_file,
    list_workspace_tree,
    read_workspace_file_content,
    search_workspace_files,
    upload_workspace_files,
    write_workspace_file_content,
)

workspace = APIRouter(prefix="/workspace", tags=["workspace"])


class CreateWorkspaceDirectoryRequest(BaseModel):
    parent_path: str
    name: str


class UpdateWorkspaceFileContentRequest(BaseModel):
    path: str
    content: str


@workspace.get("/tree", response_model=dict)
async def get_workspace_tree(
    path: str = Query("/", description="工作区目录路径"),
    recursive: bool = Query(False, description="是否递归返回子目录文件"),
    files_only: bool = Query(False, description="是否仅返回文件"),
    include_unbound_project_dirs: bool = Query(False, description="Project 选目录时展示未绑定目录"),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_workspace_tree(
        path=path,
        recursive=recursive,
        files_only=files_only,
        include_unbound_project_dirs=include_unbound_project_dirs,
        current_user=current_user,
        db=db,
    )


@workspace.get("/search", response_model=dict)
async def search_workspace_files_route(
    query: str = Query(..., description="搜索关键词"),
    current_user: User = Depends(get_required_user),
):
    return await search_workspace_files(query=query, current_user=current_user)


@workspace.get("/file")
async def get_workspace_file(
    path: str = Query(..., description="工作区文件路径"),
    current_user: User = Depends(get_required_user),
):
    return render_file_result(await read_workspace_file_content(path=path, current_user=current_user))


@workspace.put("/file", response_model=dict)
async def update_workspace_file(
    payload: UpdateWorkspaceFileContentRequest,
    current_user: User = Depends(get_required_user),
):
    return await write_workspace_file_content(
        path=payload.path,
        content=payload.content,
        current_user=current_user,
    )


@workspace.delete("/file", response_model=dict)
async def delete_workspace_file_route(
    path: str = Query(..., description="工作区文件或目录路径"),
    current_user: User = Depends(get_required_user),
):
    return await delete_workspace_path(path=path, current_user=current_user)


@workspace.post("/directory", response_model=dict)
async def create_workspace_directory_route(
    payload: CreateWorkspaceDirectoryRequest,
    current_user: User = Depends(get_required_user),
):
    return await create_workspace_directory(
        parent_path=payload.parent_path,
        name=payload.name,
        current_user=current_user,
    )


@workspace.post("/upload", response_model=dict)
async def upload_workspace_files_route(
    parent_path: str = Form(..., description="父目录路径"),
    relative_paths: list[str] | None = Form(None, description="与 files 顺序对齐的相对路径"),
    files: list[UploadFile] = File(..., description="上传文件列表"),
    current_user: User = Depends(get_required_user),
):
    try:
        inputs = await prepare_upload_files(
            files,
            max_size_bytes=MAX_WORKSPACE_UPLOAD_SIZE_BYTES,
            too_large_message="文件过大，当前仅支持 100 MB 以内的文件",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await upload_workspace_files(
        parent_path=parent_path,
        files=inputs,
        relative_paths=relative_paths,
        current_user=current_user,
    )


@workspace.get("/download")
async def download_workspace(
    path: str = Query(..., description="工作区文件路径"),
    current_user: User = Depends(get_required_user),
):
    return render_file_result(await download_workspace_file(path=path, current_user=current_user))
