// Minimal release-content check against an extracted, unmodified runtime pack.
// All Rime state belongs to the supplied temporary directory.
#include <rime_api.h>
#include <dlfcn.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>

static RimeApi* api=nullptr;
static RimeSessionId session=0;
static unsigned checks=0;
static void check(bool ok,const char* message){++checks;if(!ok)throw std::runtime_error(message);}
static std::string drain(){
    RIME_STRUCT(RimeCommit,c);std::string result;
    if(api->get_commit(session,&c)){result=c.text?c.text:"";api->free_commit(&c);}
    return result;
}
static void type(const std::string& raw){
    for(unsigned char c:raw)check(api->process_key(session,c,0),"Input key was not consumed");
}
static int position(const std::string& text){
    RIME_STRUCT(RimeContext,c);check(api->get_context(session,&c),"No candidate menu");
    int result=-1;
    for(int i=0;i<c.menu.num_candidates;++i)if(c.menu.candidates[i].text && text==c.menu.candidates[i].text)result=i;
    api->free_context(&c);return result;
}
static std::string first(){
    RIME_STRUCT(RimeContext,c);check(api->get_context(session,&c),"No candidate menu");
    std::string result=c.menu.num_candidates && c.menu.candidates[0].text?c.menu.candidates[0].text:"";
    api->free_context(&c);return result;
}
int main(int argc,char** argv){
    try{
        check(argc==6,"Usage: probe isolated-user shared lua-plugin schema-version fresh|reload");
        api=rime_get_api();check(dlopen(argv[3],RTLD_NOW|RTLD_GLOBAL)!=nullptr,"Cannot load librime-lua");
        const char* modules[]={"default","lua",nullptr};RIME_STRUCT(RimeTraits,t);
        t.user_data_dir=argv[1];t.shared_data_dir=argv[2];t.log_dir=argv[1];t.app_name="rime.tiger.runtime";t.modules=modules;
        api->setup(&t);api->initialize(&t);if(api->start_maintenance(True))api->join_maintenance_thread();
        RimeConfig config{};
        check(api->schema_open("tiger_sentence",&config),"Cannot load packaged schema");
        char version[128]={};int minimum=-1;
        check(api->config_get_string(&config,"schema/version",version,sizeof(version)) && std::string(version)==argv[4],"Wrong deployed schema version");
        check(api->config_get_int(&config,"tiger_sentence/auto_select_min_code_length",&minimum) && minimum==3,"Wrong automatic-selection default");
        api->config_close(&config);
        session=api->create_session();check(session!=0,"Cannot create session");
        check(api->select_schema(session,"tiger_sentence"),"Cannot select packaged schema");
        check(!api->get_option(session,"ascii_mode"),"Fresh schema is not Chinese");
        api->set_option(session,"tiger_sentence_early_commit",False);
        api->set_option(session,"tiger_sentence_correction_strong",True);
        type("kzjuy");
        const bool fresh=std::string(argv[5])=="fresh";
        if(fresh){
            check(first()=="滤掉","Production model/correction baseline is unavailable");
            const int target=position("淦掉");check(target>0,"Expected exact phrase is missing");
            check(api->select_candidate(session,target),"Exact phrase selection failed");
            check(drain()=="淦掉","Selected phrase was not submitted");
        }else{
            check(first()=="淦掉","Ordinary phrase learning did not survive restart");
            api->clear_composition(session);drain();
        }
        type("krkzjuy");
        check(first()=="没淦掉","Unseen prefix did not use reusable phrase learning");
        check(api->process_key(session,' ',0),"Manual commit failed");
        check(drain()=="没淦掉","Unseen-prefix phrase was not submitted");
        std::ifstream journal(std::string(argv[1])+u8"/自学习-tiger_sentence.txt",std::ios::binary);
        const std::string data((std::istreambuf_iterator<char>(journal)),std::istreambuf_iterator<char>());
        check(data.find("kzjuy")!=std::string::npos && data.find(u8"淦掉")!=std::string::npos,"Ordinary learning row was not written");
        check(data.find("fusion-v1|")==std::string::npos && data.find("exact-correction-v1|")==std::string::npos,"Retired pair row was written");
        const std::string host=api->get_version();
        api->destroy_session(session);session=0;api->finalize();
        std::cout<<"{\"status\":\"passed\",\"runtime_package_checks\":"<<checks<<",\"mode\":\""<<argv[5]
                 <<"\",\"schema_version\":\""<<version<<"\",\"librime\":\""<<host
                 <<"\",\"unseen_prefix_first\":true,\"installed_frontend_modified\":false}\n";
        return 0;
    }catch(const std::exception& e){
        std::cerr<<e.what()<<'\n';
        if(api){if(session)api->destroy_session(session);api->finalize();}
        return 1;
    }
}
