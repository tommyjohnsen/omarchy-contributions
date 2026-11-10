/* Synthetic X11 WM_CHANGE_STATE transport probe; no desktop input handling. */
#include <xcb/xcb.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
static xcb_atom_t atom(xcb_connection_t*c,const char*n){xcb_intern_atom_reply_t*r=xcb_intern_atom_reply(c,xcb_intern_atom(c,0,strlen(n),n),NULL);if(!r)exit(3);xcb_atom_t a=r->atom;free(r);return a;}
int main(int argc,char**argv){
 if(argc!=3)return 2;
 int screen_no;xcb_connection_t*c=xcb_connect(NULL,&screen_no);if(xcb_connection_has_error(c))return 3;
 xcb_screen_iterator_t i=xcb_setup_roots_iterator(xcb_get_setup(c));while(screen_no--)xcb_screen_next(&i);xcb_screen_t*s=i.data;
 xcb_window_t w=xcb_generate_id(c);uint32_t value=s->white_pixel;
 xcb_create_window(c,XCB_COPY_FROM_PARENT,w,s->root,30,30,320,200,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,s->root_visual,XCB_CW_BACK_PIXEL,&value);
 const char*title="Isolated X11 minimize transport probe";xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_NAME,XCB_ATOM_STRING,8,strlen(title),title);
 xcb_map_window(c,w);xcb_flush(c);
 for(int round=0;round<2;round++){
  const char*gate=argv[round+1];for(int n=0;access(gate,F_OK)!=0;n++){if(n>200)return 4;usleep(50000);}
  xcb_client_message_event_t e={0};e.response_type=XCB_CLIENT_MESSAGE;e.format=32;e.window=w;e.type=atom(c,"WM_CHANGE_STATE");e.data.data32[0]=round==0?3:1;
  xcb_send_event(c,0,s->root,XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT|XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,(char*)&e);xcb_flush(c);printf("WM_CHANGE_STATE %d\n",(int)e.data.data32[0]);fflush(stdout);
 }
 sleep(1);xcb_destroy_window(c,w);xcb_flush(c);xcb_disconnect(c);return 0;
}
