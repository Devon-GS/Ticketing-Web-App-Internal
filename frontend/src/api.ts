const API = '/api';
export type User = {id:number; email:string; full_name:string; role:'user'|'admin'; is_active:boolean};
export type Label = {id:number; name:string; color:string};
export type Ticket = {id:number; title:string; description:string; status:'open'|'closed'; created_at:string; closed_at:string|null; created_by:User; assigned_to:User|null; closed_by:User|null; labels:Label[]; comments:{id:number;body:string;author:User;created_at:string}[]};
export async function api<T>(path:string, options:RequestInit={}){const token=localStorage.getItem('token'); const res=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})}}); if(!res.ok) throw new Error((await res.json()).detail||'Request failed'); return res.json() as Promise<T>}
